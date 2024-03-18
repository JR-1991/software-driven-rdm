import json
import os
import re
import shutil
import uuid
import pydantic_xml
import random
import tempfile
import validators
import yaml
import warnings
import numpy as np
import hashlib

from nob import Nob
from nob.path import Path
from dotted_dict import DottedDict
from enum import Enum
from anytree import Node, LevelOrderIter
from bigtree import print_tree, levelorder_iter, yield_tree
from functools import lru_cache
from lxml.etree import _Element
from pydantic import ConfigDict, PrivateAttr, field_validator
from typing import (
    Any,
    List,
    Dict,
    Optional,
    IO,
    Tuple,
    Union,
    get_args,
    Callable,
    get_origin,
)

from sdRDM.base.importedmodules import ImportedModules
from sdRDM.base.listplus import ListPlus
from sdRDM.base.referencecheck import (
    object_is_compliant_to_references,
    value_is_compliant_to_references,
)
from sdRDM.base.utils import generate_model
from sdRDM.base.tree import _digit_free_path, build_guide_tree, ClassNode
from sdRDM.generator.codegen import generate_python_api
from sdRDM.generator.utils import extract_modules
from sdRDM.tools.utils import YAMLDumper
from sdRDM.tools.gitutils import (
    build_library_from_git_specs,
    _import_library,
)


class DataModel(pydantic_xml.BaseXmlModel):
    # * Config
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    # * Private attributes
    _node: Optional[Node] = PrivateAttr(default=None)
    _types: DottedDict = PrivateAttr(default=dict)
    _parent: Optional["DataModel"] = PrivateAttr(default=None)
    _references: DottedDict = PrivateAttr(default_factory=DottedDict)
    _id: Optional[str] = PrivateAttr(default_factory=uuid.uuid4)
    _attribute: Optional[str] = PrivateAttr(default=None)

    def __init__(self, **data):
        self._convert_units(self, data)
        self._convert_mathml(self, data)
        self._convert_equation(self, data)

        super().__init__(**data)
        self._initialize_references()

        for name, value in data.items():
            if bool(re.match("_[a-zA-Z0-9]*", name)):
                continue

            # Store references to other objects and vice versa
            # self._add_reference_to_object(name, value)

        for field, value in self.__dict__.items():
            is_object = hasattr(value, "model_fields")
            is_list = isinstance(value, (list, ListPlus))

            if is_list:
                is_object = all([self.is_data_model(v) for v in value])

            if not is_object and not is_list:
                continue
            elif not is_object and is_list:
                continue

            self.__dict__[field]._parent = self
            self.__dict__[field]._attribute = field

        self._types = DottedDict()
        for name, field in self.model_fields.items():
            args = get_args(field.annotation)

            if not args and hasattr(field.annotation, "model_fields"):
                self._types[name] = field.annotation
            elif args:
                self._types[name] = tuple(
                    [subtype for subtype in args if hasattr(subtype, "model_fields")]
                )

    def _initialize_references(self):
        """Initialized references for each field present in the data model"""
        for field in self.model_fields.values():
            self._references[field] = ListPlus()

    # ! Getters
    def get(
        self,
        path: str,
        attribute: Optional[str] = None,
        target: Union[str, float, int, None, "DataModel", Callable] = None,
    ):
        if isinstance(path, Path):
            path = str(path)

        # Remove trailing slash
        path = path.rstrip("/")

        if not path.startswith("/") and len(path.split("/")) > 1:
            path = f"/{path}"

        if not bool(re.search(r"\/\d*\/", path)):
            return self._get_by_meta_path(path, attribute, target)

        return self._get_by_absolute_path(path, attribute, target)

    def _get_by_absolute_path(
        self,
        path: str,
        attribute: Optional[str] = None,
        target: Union[str, float, int, None, "DataModel", Callable] = None,
    ):
        """Helper function to search for a given path in the model"""

        query = self._setup_query(target)
        model = Nob(self.to_dict(warn=False, convert_h5ds=False))

        path = model.find(path)

        assert path, f"Path '{path}' does not exist in the model."

        object = self._traverse_model_by_path(self, path[0])

        return self._check_query(object, attribute, query)

    def _get_by_meta_path(
        self: "DataModel",
        path: str,
        attribute: Optional[str] = None,
        target: Optional[str] = None,
    ) -> List["DataModel"]:
        """Returns all obejcts or values found via the meta path and instance"""

        if not path.startswith("/"):
            path = "/" + path

        # Get all the paths that end with the last part
        last_part = path.split("/")[-1].strip("/")
        model = Nob(self.to_dict(warn=False, convert_h5ds=False))
        query = self._setup_query(target)

        paths = model.find(last_part)
        matching_paths = [p for p in paths if _digit_free_path(str(p)) == path]

        references = ListPlus()
        for path in matching_paths:  # type: ignore
            reference = self._check_query(
                self._traverse_model_by_path(self, path),
                attribute,
                query,
            )

            if reference is not None:
                references.append(reference)

        return references

    @staticmethod
    def _setup_query(
        target: Union[str, float, int, None, "DataModel", Callable]
    ) -> Optional[Callable]:
        """Sets up a query function that can be used to filter values"""

        if not isinstance(target, Callable) and target is not None:
            return lambda x: x == target
        elif target is None:
            return None

        return target

    def _check_query(
        self,
        value: Any,
        attribute: Optional[str],
        query: Optional[Callable],
    ):
        """Performs a query on a given object and attribute"""

        # No query given
        if query is None:
            return value

        is_list = isinstance(value, (list, ListPlus))
        is_all_objects = (
            all([self.is_data_model(v) for v in value]) if is_list else False
        )
        is_object = self.is_data_model(value)

        # Object case
        if is_object and not is_list:
            return self._query_object(value, attribute, query)
        elif is_all_objects and is_list:
            l = ListPlus()
            for v in value:
                if self._query_object(v, attribute, query):
                    l.append(v)
            return l
        elif is_list:
            return ListPlus([v for v in value if query(v)])
        else:
            if query(value):
                return value

    @staticmethod
    def _query_object(
        obj: "DataModel",
        attribute: Optional[str],
        query: Callable,
    ):
        assert attribute is not None, f"Attribute must be specified for query."

        if not hasattr(obj, attribute):
            raise ValueError(
                f"Object '{obj.__class__.__name__}' does not have attribute '{attribute}'"
            )

        if query(getattr(obj, attribute)):
            return obj

    def _traverse_model_by_path(self, object, path):
        """Traverses a give sdRDM model by using a path"""

        # Split path into commands
        commands = str(path).strip("/").split("/")

        current = self
        for command in commands:
            if command.isdigit():
                current = current[int(command)]  # type: ignore
            else:
                current = getattr(current, command)

        return current

    def paths(self, leaves: bool = False):
        """Returns all possible paths of an instantiated data model. Can also be reduced to just leaves."""

        # Get JSON representation
        model = Nob(self.to_dict(warn=False, mode="python"))

        if leaves:
            return model.leaves
        else:
            return model.paths

    @classmethod
    def meta_paths(cls, leaves: bool = False):
        """Returns all possible paths of an instantiated data model. Can also be reduced to just leaves."""

        metapaths = set()
        for node in LevelOrderIter(cls.meta_tree(show=False)):
            if len(node.node_path) == 1:
                continue

            if leaves and node.is_leaf:
                metapaths.add(
                    "/".join([n.name for n in node.node_path if n.name[0].islower()])
                )
            elif not leaves:
                metapaths.add(
                    "/".join([n.name for n in node.node_path if n.name[0].islower()])
                )

        return sorted(metapaths)

    def _meta_path(self):
        """
        Returns the meta path of the DataModel object.

        The meta path is a string representation of the path from the root DataModel object to the current object.
        It is constructed by traversing the parent-child relationship of the objects and appending the attribute names
        to the path.

        Returns:
            str: The meta path of the DataModel object.
        """

        if not self._attribute or not self._parent:
            return self.__class__.__name__

        path = []
        obj = self

        while True:
            if not obj._parent:
                path.append(type(obj).__name__)
                break

            path.append(obj._attribute)
            obj = obj._parent

        return "/".join(path[::-1])

    # ! Exporters
    def to_dict(
        self,
        exclude_none=True,
        warn=True,
        convert_h5ds=True,
        mode="json",
        **kwargs,
    ):

        data = super().model_dump(
            exclude_none=exclude_none,
            by_alias=True,
            mode=mode,
            **kwargs,
        )

        # Convert all ListPlus items back to normal lists
        # to stay compliant to PyDantic
        data = self._convert_types_and_remove_empty_objects(
            data,
            exclude_none,
            convert_h5ds,
        )

        try:
            # Add git specs if available
            data["__source__"] = {
                "root": self.__class__.__name__,
                "repo": self._repo,  # type: ignore
                "commit": self._commit,  # type: ignore
                "url": self._repo.replace(".git", "") + f"/tree/{self._commit}",  # type: ignore
            }  # type: ignore
        except AttributeError:
            if warn:
                warnings.warn(
                    "No 'URL' and 'Commit' specified. This model might not be re-usable."
                )

        return data

    def _convert_types_and_remove_empty_objects(self, data, exclude_none, convert_h5ds):
        """Converts als ListPlus items back to lists."""

        nu_data = {}

        if not isinstance(data, dict):
            return data

        for key, value in data.items():
            if isinstance(value, ListPlus):
                if not value and exclude_none:
                    continue

                nu_data[key] = [
                    self._check_and_convert_sub(element, exclude_none, convert_h5ds)
                    for element in value
                ]

            elif isinstance(value, (dict)):
                if not value and exclude_none:
                    continue
                elif self._is_empty(value):
                    continue

                if self._convert_types_and_remove_empty_objects(
                    value, exclude_none, convert_h5ds
                ):
                    nu_data[key] = self._convert_types_and_remove_empty_objects(
                        value, exclude_none, convert_h5ds
                    )

            elif isinstance(value, np.ndarray):
                nu_data[key] = value.tolist()

            else:
                nu_data[key] = value

        return nu_data

    def _is_empty(self, value):
        """Checks whether this object is just made up by its ID"""

        if not isinstance(value, dict):
            return False

        is_empty = []

        for name, attribute in value.items():
            if name == "id":
                continue

            if isinstance(attribute, list):
                is_empty.append(len(attribute) == 0)
            elif isinstance(attribute, dict):
                is_empty.append(self._is_empty(attribute))
            else:
                is_empty.append(attribute == None)

        return all(is_empty)

    def _check_and_convert_sub(self, element, exclude_none, convert_h5ds):
        """Helper function used to trigger recursion on deeply nested lists."""

        if isinstance(element, np.ndarray):
            return element

        if element.__class__.__module__ == "builtins" and not isinstance(element, dict):
            return element

        return self._convert_types_and_remove_empty_objects(
            element, exclude_none, convert_h5ds
        )

    def json(self, indent: int = 2, **kwargs):
        return json.dumps(
            self.to_dict(**kwargs),
            indent=indent,
            default=self._json_dump,
        )

    @staticmethod
    def _json_dump(value):
        """Helper function to export nd-arrays in a proper way"""

        if isinstance(value, np.ndarray):
            return value.tolist()

        return str(value)

    def yaml(self, **kwargs):
        return yaml.dump(
            self.to_dict(**kwargs),
            Dumper=YAMLDumper,
            default_flow_style=False,
            sort_keys=False,
        )

    def xml(self, skip_empty: bool = False):
        return self.to_xml(
            pretty_print=True,
            encoding="UTF-8",
            skip_empty=skip_empty,
            xml_declaration=True,
        ).decode()  # type: ignore

    def hdf5(self, file: Union["H5File", str]) -> None:
        """Writes the object instance to HDF5."""

        try:
            from sdRDM.base.ioutils.hdf5 import write_hdf5
        except ImportError:
            raise ImportError(
                "HDF5 is not installed. Please install it via 'pip install h5py'"
            )

        write_hdf5(self, file)

    # ! Inherited Initializers
    @classmethod
    def from_dict(cls, obj: Dict):
        return cls.model_validate(obj)

    @classmethod
    def from_json_string(cls, json_string: str):
        return cls.from_dict(json.loads(json_string))

    @classmethod
    def from_json(cls, handler: IO):
        return cls.from_dict(json.load(handler))

    @classmethod
    def from_yaml_string(cls, yaml_string: str):
        return cls.from_dict(yaml.safe_load(yaml_string))

    @classmethod
    def from_yaml(cls, handler: IO):
        return cls.from_dict(yaml.safe_load(handler))

    @classmethod
    def from_xml(cls, handler: IO):
        return super().from_xml(handler.read())

    @classmethod
    def from_xml_string(cls, xml_string: str):
        return super().from_xml(xml_string)

    @classmethod
    def from_hdf5(cls, file):
        """Reads a hdf5 file from path into the class model."""

        try:
            from sdRDM.base.ioutils.hdf5 import read_hdf5
        except ImportError:
            raise ImportError(
                "HDF5 is not installed. Please install it via 'pip install h5py'"
            )

        return read_hdf5(cls, file)

    # ! Dynamic initializers
    @classmethod
    def parse(
        cls,
        path: Optional[str] = None,
        data: Optional[Dict] = None,
        root_name: str = "Root",
        attr_replace: str = "",
    ):
        """Reads an arbitrary format and infers the corresponding object model to load the data.

        This function is used to open legacy files or any other file where the software
        is not known. In addition, this function allows you to load any sdRDM capable
        format without having to install a library.

        Args:
            path (str): Path to the file to load.
            data (Dict): Dataset in dict format.
            root_name (str): Name of the root element. Defaults to 'Root'
            attr_replace (str): When the given data model keys contain a pattern to replace for readability. Defaults to empty string.
        """

        # Detect base
        if path and data is None:
            if cls._is_json(path):
                dataset = json.loads(open(path).read())
            elif cls._is_yaml(path):
                dataset = yaml.safe_load(open(path).read())
            elif cls._is_hdf5(path):
                import deepdish as dd

                dataset = dd.io.load(path)
            else:
                raise TypeError("Base format is unknown!")
        elif data and path is None:
            dataset = data
        elif data and path:
            raise ValueError(
                f"Data and path have been specified. Please use only one of the arguments to parse live data ('data') or file data ('path')"
            )
        else:
            raise ValueError(
                f"Neither path nor data have been specified. Either of both should be specified."
            )

        # Check if there is a source reference
        if "__source__" not in dataset:
            # If no source is given, just create a model
            # from the blank dataset -> Can be incomplete
            lib = generate_model(
                data=dataset,
                name=root_name,
                base=cls,
                attr_replace=attr_replace,
            )
            root = getattr(lib, root_name)
            return root.from_dict(dataset), lib
        else:
            # Get source and build libary
            url = dataset.get("__source__")["repo"]
            commit = dataset.get("__source__")["commit"]
            root = dataset.get("__source__")["root"]
            lib = cls.from_git(url=url, commit=commit)

            # Use the internal librar to parse the file
            return getattr(lib, root).from_dict(dataset), lib  # type: ignore

    @staticmethod
    def _is_json(path: str):
        try:
            json.loads(open(path).read())
        except ValueError as e:
            return False
        return True

    @staticmethod
    def _is_yaml(path: str):
        try:
            yaml.safe_load(open(path).read())
        except ValueError as e:
            return False
        return True

    @staticmethod
    def _is_hdf5(path: str):
        try:
            import deepdish as dd
            from tables.exceptions import HDF5ExtError
        except ImportError:
            raise ImportError(
                "HDF5 is not installed. Please install it via 'pip install h5py deepdish'"
            )

        try:
            dd.io.load(path)
        except HDF5ExtError as e:
            return False

        return True

    @classmethod
    def from_markdown(cls, path: str) -> ImportedModules:
        """Converts a markdown file into a in-memory Python API.

        Args:
            path (str): Path to the markdown file.
        """

        with tempfile.TemporaryDirectory() as tmpdirname:
            # Generate API to parse the file
            lib_name = f"sdRDM-Library-{str(random.randint(0,30))}"
            api_loc = os.path.join(tmpdirname, lib_name)
            generate_python_api(
                path=path,
                dirpath=tmpdirname,
                libname=lib_name,
                use_formatter=False,
            )

            lib = _import_library(api_loc, lib_name)

        return extract_modules(lib=lib, links={})

    @classmethod
    @lru_cache(maxsize=128)
    def from_git(
        cls,
        url: str,
        commit: Optional[str] = None,
        tag: Optional[str] = None,
        only_classes: bool = False,
    ) -> ImportedModules:
        """Fetches a Markdown specification from a git repository and builds the library accordingly.

        This function will clone the repository into a temporary directory and
        builds the correpsonding API and loads it into the memory. After that
        the cloned repository is deleted and the root object(s) detected.

        Args:
            url (str): Link to the git repository. Use the URL ending with ".git".
            commit (Optional[str], optional): Hash of the commit to fetch from. Defaults to None.
            tag (Optional[str], optional): Tag of the release or branch to fetch from. Defaults to None.
            only_classes (bool, optional): If True, only the classes will be returned. Defaults to False.
        """

        if not validators.url(url):
            raise ValueError(f"Given URL '{url}' is not a valid URL.")

        # Build and import the library
        tmpdirname = tempfile.mkdtemp()

        try:
            lib, links = build_library_from_git_specs(
                url=url,
                tmpdirname=tmpdirname,
                commit=commit,
                tag=tag,
                only_classes=only_classes,
            )
        except Exception as e:
            # At any exception catch it and remove the tempdir
            shutil.rmtree(tmpdirname, ignore_errors=True)
            raise e
        finally:
            # At success, also remove it
            shutil.rmtree(tmpdirname, ignore_errors=True)

        if only_classes:
            return lib

        return extract_modules(lib, links)

    @staticmethod
    def _find_root_objects(classes: Dict):
        """Parses a given library and returns the root object(s)

        Root objects are assumed to be objects that are not part of
        another class yet possess other objects/attributes.
        """

        for definition in classes.values():
            for field in definition.cls.model_fields.values():
                if "Union" not in repr(field.annotation) and issubclass(
                    field.annotation, DataModel
                ):
                    classes[field.annotation.__name__].add_parent_class(definition)

        roots = list(
            filter(lambda definition: not definition.parent_classes, classes.values())
        )

        return [root.cls for root in roots]

    # ! Utilities
    @classmethod
    def meta_tree(
        cls,
        show: bool = True,
        max_depth: int = 0,
    ):
        """Builds a tree structure from the class definition and all decending types."""
        tree = build_guide_tree(cls)

        if show:
            print_tree(tree, max_depth=max_depth)

        return tree

    def tree(
        self,
        show: bool = True,
        values: bool = True,
        max_depth: int = 0,
    ):
        """Builds a tree structure from the class definition and all decending types."""
        tree = build_guide_tree(self)

        if show:
            show_tree = self._prune_tree(tree)
            print_tree(
                show_tree,
                attr_list=["value"] if values else [],
                max_depth=max_depth,
            )

        return tree

    def _prune_tree(self, tree: ClassNode):
        """Prunes leaves that have no value given"""
        for node in levelorder_iter(tree):
            if hasattr(node, "value") and node.value is None and not node.children:
                node.children = []
                node.parent = None

        return tree

    # ! Validators
    @field_validator("*")
    @classmethod
    def _convert_extended_list_and_numpy_strings(cls, value):
        """Validator used to convert any list into a ListPlus."""

        if isinstance(value, list):
            return ListPlus(*[cls._convert_numpy_type(v) for v in value], in_setup=True)
        elif isinstance(value, np.str_):
            return str(value)
        else:
            return value

    @field_validator("*", mode="before")
    def _convert_lists_to_ndarray(cls, value, info):
        field_type = cls.model_fields[info.field_name].annotation
        if cls._has_ndarray(field_type) and isinstance(value, list):
            return np.array(value)

        return value

    @staticmethod
    def _has_ndarray(dtype):
        return any(
            t.__name__ == "ndarray" for t in get_args(dtype) if hasattr(t, "__name__")
        )

    @staticmethod
    def _convert_numpy_type(value):
        """Helper function to convert numpy strings into builtin"""
        if isinstance(value, np.str_):
            return str(value)

        return value

    def validate_references(self):
        """Recursively validates this object and all sub-objects"""

        report = {}

        for _, value in self:
            if not self.is_data_model(value):
                continue

            if isinstance(value, list):
                for subvalue in value:
                    report.update(subvalue.validate_references())
                continue

            report.update(value.validate_references())

        return report

    @field_validator("*")
    @classmethod
    def check_list_values(cls, values, info):
        if not isinstance(values, (list, ListPlus)):
            return values

        field_type = cls.model_fields[info.field_name].annotation

        if get_args(field_type):
            field_type = get_args(field_type)
        else:
            field_type = [field_type]

        for value in values:
            checks = [
                cls._check_list_value(value, dtype)
                for dtype in field_type
                if dtype != type(None)
            ]

            if not any([check[1] for check in checks]):
                error_messages = "\n".join(
                    [msg for msg, check in checks if check is False]
                )
                raise TypeError(error_messages)

        return values

    @staticmethod
    def _check_list_value(value: Any, field_type) -> Tuple[str, bool]:
        msg = f"List element of type '{type(value)}' cannot be added. Expected type '{field_type}'"

        # Todo: Fix 3.9 compatibility for generics
        # if not isinstance(value, field_type) and not hasattr(value, "__members__"):
        #     return msg, False

        return "", True

    @field_validator("*", mode="before")
    @classmethod
    def convert_numpy_to_appropriate_type(cls, value, info):
        """Converts numpy arrays to the appropriate native numeric type, if possible."""

        field_type = cls.model_fields[info.field_name].annotation

        if not isinstance(value, np.ndarray):
            # Skip if not a numpy array
            return value

        is_multiple = get_origin(field_type) is list
        is_numeric = any(dtype in (int, float) for dtype in get_args(field_type))

        if not is_numeric:
            return value

        if isinstance(value, np.ndarray) and is_multiple:
            return value.tolist()
        elif isinstance(value, np.ndarray) and not is_multiple:
            return field_type(value)

        return value

    # ! Pre-validators
    # TODO Generalize pre validators
    def _convert_units(self, model, data):
        unit_fields = [
            name
            for name, field in model.model_fields.items()
            if self._is_unit_type(field)
        ]

        for name in unit_fields:
            if name not in data:
                continue

            data[name] = self._convert_unit_string_to_unit_type(data[name])

    @staticmethod
    def _is_unit_type(field):
        from sdRDM.base.datatypes import Unit

        if field.annotation == Unit:
            return True

        return any(dtype == Unit for dtype in get_args(field.annotation))

    @staticmethod
    def _convert_unit_string_to_unit_type(units):
        from sdRDM.base.datatypes import Unit

        if not isinstance(units, (list, ListPlus)):
            is_list = False
            units = [units]
        else:
            is_list = True

        converted = []
        for unit in units:
            if isinstance(unit, str) and unit != "":
                converted.append(Unit.from_string(unit))
            elif isinstance(unit, str) and unit == "":
                converted.append(None)
            else:
                converted.append(unit)

        if is_list:
            return converted
        else:
            return converted[0]

    def _convert_mathml(self, model, data):
        mathml_fields = [
            name
            for name, field in model.model_fields.items()
            if self._is_mathml_type(field)
        ]

        for name in mathml_fields:
            if name not in data:
                continue

            data[name] = self._convert_mathml_string_to_mathml_type(data[name])

    @staticmethod
    def _is_mathml_type(field):
        from sdRDM.base.datatypes import MathML

        if field.annotation == MathML:
            return True

        return any(dtype == MathML for dtype in get_args(field.annotation))

    @staticmethod
    def _convert_mathml_string_to_mathml_type(mathmls):
        from sdRDM.base.datatypes import MathML

        if not isinstance(mathmls, (list, ListPlus)):
            is_list = False
            mathmls = [mathmls]
        else:
            is_list = True

        converted = []
        for mathml in mathmls:
            if isinstance(mathml, str) and mathml != "":
                converted.append(MathML.from_equation(mathml))
            elif isinstance(mathml, str) and mathml == "":
                converted.append(None)
            else:
                converted.append(mathml)

        if is_list:
            return converted
        else:
            return converted[0]

    def _convert_equation(self, model, data):
        equation_fields = [
            name
            for name, field in model.model_fields.items()
            if self._is_equation_type(field)
        ]

        for name in equation_fields:
            if name not in data:
                continue

            data[name] = self._convert_equation_string_to_equation_type(data[name])

    @staticmethod
    def _is_equation_type(field):
        from sdRDM.base.datatypes import Equation

        if field.annotation == Equation:
            return True

        return any(dtype == Equation for dtype in get_args(field.annotation))

    @staticmethod
    def _convert_equation_string_to_equation_type(equations):
        from sdRDM.base.datatypes import Equation

        if not isinstance(equations, (list, ListPlus)):
            is_list = False
            equations = [equations]
        else:
            is_list = True

        converted = []
        for equation in equations:
            if isinstance(equation, str) and equation != "":
                converted.append(Equation(equation))
            elif isinstance(equation, str) and equation == "":
                converted.append(None)
            else:
                converted.append(equation)

        if is_list:
            return converted
        else:
            return converted[0]

    # ! Overloads
    def __setattr__(self, name, value):
        if bool(re.match("_[a-zA-Z0-9]*", name)):
            return super().__setattr__(name, value)

        if self._is_unit_type(self.model_fields[name]):
            value = self._convert_unit_string_to_unit_type(value)

        self._add_reference_to_object(name, value)
        self._set_parent_instances(value)
        self._check_references(name, value)

        super().__setattr__(name, value)

        if isinstance(value, (list, ListPlus)):
            self.__dict__[name]._parent = self
            self.__dict__[name]._attribute = name

    def _add_reference_to_object(self, name, value):
        """Adds the current class to the referenced object to maintain its relation"""

        if name.startswith("_"):
            return

        extra = self.model_fields[name].json_schema_extra

        if extra is None:
            return
        elif "reference" not in extra:
            return
        elif not hasattr(value, "model_fields"):
            return

        # Add the relation to the attribute of this field
        self._references[name].append(value)

        # Also add it to the other object
        target_attr = extra["reference"].split(".")[-1]
        value._references[target_attr].append(self)

    def _check_references(self, name, value):
        """Checks whether references are compliant"""

        if self.is_data_model(value):
            report = self.check_object_references(value)
        else:
            report = self.check_value_references(name, value)

        if report != {}:
            rendered_report = "\n\n".join(
                [f"- {message}" for message in report.values()]
            )
            raise ValueError(
                f"""Object is not compliant to the model:
                
            {rendered_report}
                """
            )

    def _set_parent_instances(self, value) -> None:
        """Sets current instance as the parent to objects"""
        if isinstance(value, ListPlus):
            value._parent = self
            for i in range(len(value)):
                self.set_parent_to_object_field(value[i])
        else:
            self.set_parent_to_object_field(value)

    def set_parent_to_object_field(self, value):
        """Sets a reference to the parent element found in the data model"""

        if not hasattr(value, "model_fields"):
            return

        value._parent = self

    def check_object_references(self, value) -> Dict:
        """Checks if any (sub)-object fulfills the conditions of the model"""

        report = {}

        if isinstance(value, list):
            for i in range(len(value)):
                report.update(object_is_compliant_to_references(value[i]))

            return report

        else:
            return object_is_compliant_to_references(value)

    def check_value_references(self, attribute, value) -> Dict:
        """Checks if a value assigned to this object is compliant to references"""

        report = {}

        if isinstance(value, list):
            for i in range(len(value)):
                report.update(
                    value_is_compliant_to_references(attribute, value[i], self)
                )

            return report

        else:
            return value_is_compliant_to_references(attribute, value, self)

    def is_data_model(self, value) -> bool:
        """Checks whether this object is of type 'DataModel'"""

        if isinstance(value, list):
            return all(hasattr(subval, "model_fields") for subval in value)

        return hasattr(value, "model_fields")

    # ! Dunder methods
    def __hash__(self) -> int:
        """Hashes the object based on its `dict` content"""

        data = [f"{key}={dict(self)[key]}" for key in sorted(dict(self).keys())]  # type: ignore
        data_string = "".join(data)

        return hashlib.md5(data_string.encode()).hexdigest()

    def __eq__(self, __value: object) -> bool:
        """Compares two objects based on their hashes"""

        try:
            __value.__hash__()
        except TypeError:
            raise TypeError(
                f"Can't compare '{self.__class__.__name__}' to type '{type(__value)}'"
            )
        return self.__hash__() == __value.__hash__()

    def __str__(self) -> str:
        class bcolors:
            HEADER = "\033[95m"
            OKBLUE = "\033[94m"
            OKCYAN = "\033[96m"
            OKGREEN = "\033[92m"
            WARNING = "\033[93m"
            FAIL = "\033[91m"
            ENDC = "\033[0m"
            BOLD = "\033[1m"
            UNDERLINE = "\033[4m"

        tree = self._prune_tree(self.tree(show=False))
        tree_string = ""

        for branch, stem, node in yield_tree(tree, style="const"):
            if hasattr(node, "value") and node.value is not None:
                if isinstance(node.value, (list, ListPlus)):
                    value = f"[{', '.join([str(v) for v in node.value[0:5]])}, ...]"
                else:
                    value = str(node.value)

                tree_string += f"{branch}{stem}{bcolors.OKBLUE}{node.node_name}{bcolors.ENDC} = {value}\n"
            elif hasattr(node, "value") and node.value is None:
                tree_string += (
                    f"{branch}{stem}{bcolors.OKBLUE}{node.node_name}{bcolors.ENDC}\n"
                )
            elif node.name.isdigit():
                tree_string += f"{branch}{stem}{node.node_name}\n"
            else:
                tree_string += (
                    f"{branch}{stem}{bcolors.UNDERLINE}{node.node_name}{bcolors.ENDC}\n"
                )

        return tree_string

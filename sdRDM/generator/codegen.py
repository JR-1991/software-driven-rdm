import glob
import os
import re
import jinja2
import json
import subprocess
import sys

from importlib import resources as pkg_resources
from joblib import Parallel, delayed
from operator import itemgetter
from typing import Dict, Optional

from sdRDM.generator.mermaidclass import MermaidClass
from sdRDM.generator.mermaidenum import MermaidEnum
from sdRDM.generator.mermaidexternal import MermaidExternal
from sdRDM.tools.gitutils import build_library_from_git_specs
from sdRDM.generator.schemagen import generate_schema, Format
from sdRDM.generator import templates as jinja_templates
from sdRDM.generator.utils import preserve_custom_functions

FORMAT_MAPPING: Dict[str, Format] = {"md": Format.MARKDOWN}
GITHUB_TYPE_PATTERN = r"(http[s]?://[www.]?github.com/[A-Za-z0-9\/\-\.]*[.git]?)"


def generate_python_api(
    path: str,
    out: str,
    name: str,
    url: Optional[str] = None,
    commit: Optional[str] = None,
    only_classes: bool = False,
):

    # Create library directory
    lib_path = os.path.join(out, name)
    core_path = os.path.join(lib_path, "core")
    schema_path = os.path.join(lib_path, "schemes")

    os.makedirs(core_path, exist_ok=True)

    # Add __init__ for module compliance
    init_lib_template = jinja2.Template(
        pkg_resources.read_text(jinja_templates, "init_file_library.jinja2")
    )
    with open(os.path.join(lib_path, "__init__.py"), "w") as f:
        if all([url, commit]):
            f.write(init_lib_template.render(url=url, commit=commit))

    # Read and find all files
    if os.path.isdir(path):
        specifications = list(glob.glob(os.path.join(path, "*")))
        is_single = len(specifications) == 1
    elif os.path.isfile(path):
        specifications = [path]
        is_single = True
    else:
        raise TypeError(f"Given path '{path}' is neither a file nor a directory.")

    # Store the class definitions to return those
    cls_defs = {}

    for file in specifications:
        extension = os.path.basename(file).split(".")[-1]

        if extension not in FORMAT_MAPPING:
            pass

        # Generate schemata
        format_type = FORMAT_MAPPING[extension]
        mermaid_path, metadata_path = generate_schema(
            open(file, "r"), schema_path, format_type
        )

        # Generate the API
        cls_defs = write_module(
            schema=mermaid_path,
            descriptions_path=metadata_path,
            out=core_path,
            is_single=is_single,
            url=url,
            commit=commit,
            only_classes=only_classes,
        )

    return cls_defs


def write_module(
    schema: str,
    descriptions_path: str,
    out: str,
    is_single: bool = False,
    commit: Optional[str] = None,
    url: Optional[str] = None,
    only_classes: bool = False,
) -> Optional[Dict[str, MermaidClass]]:
    """Renders and writes a module based on a Mermaid schema

    Steps:

        1. Extract all class definitions including imports and attributes
        2. Build a dependency tree to traverse later on
        3. Render, write and re-format given classes

    Args:
        schema (str): Path to the Mermaid class diagram
        descriptions (str): Path to the descriptions JSON
        out (str): Path to the target module folder
    """

    # (0) Build target path
    if is_single:
        path = out
    else:
        path = os.path.join(out, os.path.basename(schema).split(".")[0])
    descriptions: Dict = json.loads(open(descriptions_path).read())
    os.makedirs(path, exist_ok=True)

    # (1) Get class definitions
    class_defs = get_class_definitions(schema, descriptions)

    if only_classes:
        return class_defs

    # (2) Build dependency tree
    tree = create_dependency_tree(open(schema).read())

    # (3) Render, write and re-format classes
    write_class(tree=tree, classes=class_defs, dirpath=path, url=url, commit=commit)

    # (5) Finally, write the __init__ file
    init_path = os.path.join(path, "__init__.py")
    with open(init_path, "w") as f:
        module_init = render_dunder_init(
            classes=class_defs, module_doc=descriptions.get("docstring")
        )
        f.write(module_init)

    subprocess.run([sys.executable, "-m", "black", "-q", init_path])


def get_class_definitions(path: str, descriptions) -> Dict[str, MermaidClass]:
    """Retrieves the individual class definitions from a mermaid diagram"""

    cls_string = open(path).read()
    classes = cls_string.split("class ")[1::]
    definitions = {}
    for cls_def in classes:

        if "<< Enumeration >>" in cls_def:
            name = cls_def.split("{")[0].strip()
            values = cls_def.split("        +")[1:-1]
            cls_def = MermaidEnum(name=name, values=values)
        elif "<< External Object >>" in cls_def:
            cls_def = _process_external_object(cls_def, definitions)
        else:
            cls_def = MermaidClass.parse(cls_def, descriptions)

        definitions[cls_def.name] = cls_def

    return definitions


def _process_external_object(cls_def: str, definitions: Dict):
    """Processes an external object that has been supplied as a link to a GitHub repository"""

    # Get metadata and class definitions
    name = cls_def.split("{")[0].strip()
    repo = re.findall(GITHUB_TYPE_PATTERN, cls_def)[0]
    cls_defs = build_library_from_git_specs(url=repo, only_classes=True)
    target = cls_defs[name]

    # Fetch all the sub data types to include these into the build
    dtypes = _get_object_types(cls_def=target, definitions=cls_defs)

    # Add all definitions to the current APIs
    definitions.update(
        {cls_def.name: cls_def for cls_def in map(cls_defs.get, list(dtypes))}
    )

    return target


def _get_object_types(cls_def, definitions, dtypes=None):
    if dtypes is None:
        dtypes = set()

    for attr in cls_def.attributes.values():
        dtype = re.sub(r"List|Dict|\[|\]", "", attr["dtype"])
        if dtype in definitions:
            dtypes.add(dtype)
            _get_object_types(
                cls_def=definitions[dtype], definitions=definitions, dtypes=dtypes
            )

    return dtypes


def create_dependency_tree(mermaid: str):
    """Creates a dependency tree for the data model"""

    # Parse the raw mermaid file to extract all inheritances (<--)
    relation_regex = re.compile(r"([a-zA-Z]*) <-- ([a-zA-Z]*)")
    relations = relation_regex.findall(mermaid)
    results = {}

    while len(relations) > 0:

        # Create a tree from relations
        nodes = {}
        root = next(
            iter(
                set(start for start, _ in relations) - set(end for _, end in relations)
            )
        )
        for start, end in relations:
            nodes.setdefault(start, {})[end] = nodes.setdefault(end, {})

        result = {root: nodes[root]}

        # Get all those classes that have already been found
        # in the first iteration of the tree building
        used_classes = [name for name in get_keys(result)]

        # Remove all those relations that included the root
        relations = list(
            filter(lambda relation: relation[1] not in used_classes, relations)
        )

        results.update(result)

    return results


def get_keys(dictionary):
    """Recursion to traverse through nested dictionaries"""
    keys = []

    for key, item in dictionary.items():
        keys.append(key)
        if item != {}:
            keys += get_keys(item)
    return keys


def write_class(tree: dict, classes: dict, dirpath: str, url, commit):
    """Writes all classes in a parallel manner"""

    _distribute_inheritance(
        tree=tree,
        classes=classes,
    )

    kwargs = {
        "classes": classes,
        "dirpath": dirpath,
        "url": url,
        "commit": commit,
    }

    Parallel(n_jobs=-1)(
        delayed(_write_classes)(cls_obj=cls_obj, **kwargs)
        for cls_obj in classes.values()
    )


def _distribute_inheritance(
    tree: dict,
    classes: dict,
):
    """Parses the dependency tree and assigns class that is to inherit"""
    for cls_name, sub_cls in tree.items():
        for cls in sub_cls.keys():
            classes[cls].inherit = classes[cls_name]


def _write_classes(cls_obj, classes: dict, dirpath: str, url, commit):

    if isinstance(cls_obj, MermaidEnum):
        # Enums do not possess sub classes so they can be directly rendered
        _render_class(cls_obj, dirpath, classes=classes, url=url, commit=commit)
        return
    elif isinstance(cls_obj, MermaidExternal):
        # Write external objects to the generated software
        path = os.path.join(dirpath, f"{cls_obj.fname}.py")
        with open(path, "w") as f:
            f.write(cls_obj.render())

        return

    # First, check if all arbitrary types exist
    # if not render them to a file
    for sub_class in cls_obj.sub_classes:

        try:
            sub_class = classes[sub_class]
        except KeyError:
            raise ValueError(
                f"Cant locate object \033[1m{sub_class}\033[0m in specifications. Please make sure to include this object in your file."
            )

        cls_obj.imports.add(f"from .{sub_class.fname} import {sub_class.name}")

    # Finally, render the given class
    _render_class(cls_obj, dirpath, classes=classes, url=url, commit=commit)


def _render_class(cls_obj, dirpath, classes, url, commit):
    """Renders imports, attributes and methods of a class"""

    path = os.path.join(dirpath, cls_obj.fname + ".py")
    if isinstance(cls_obj, MermaidClass):
        rendered_class = _render_data_class(cls_obj, classes, url, commit)
    elif isinstance(cls_obj, MermaidEnum):
        rendered_class = cls_obj.render()
    else:
        raise TypeError(f"Class object of type '{type(cls_obj)}' is not supported.")

    if os.path.exists(path):
        rendered_class = preserve_custom_functions(rendered_class, path)

    with open(path, "w") as file:
        file.write(rendered_class)

    # Call black to format everything
    subprocess.run([sys.executable, "-m", "black", "-q", "--preview", path])


def _render_data_class(cls_obj, classes, url, commit):
    """Renders a given functional data class to a string that will be written to a file"""

    # Check if there are any sub classes in the attributes
    # that do not have any required field and thus can be
    # set as a default factory
    _set_optional_classes_as_default_factories(cls_obj, classes)

    attributes = cls_obj._render_class_attrs(
        inherit=cls_obj.inherit, url=url, commit=commit
    )
    add_methods = cls_obj._render_add_methods(classes=classes)
    imports = cls_obj._render_imports(inherits=cls_obj.inherit)

    if add_methods:
        return f"{imports}\n{attributes}\n{add_methods}"
    else:
        return f"{imports}\n{attributes}"


def _set_optional_classes_as_default_factories(cls_obj, classes):
    """Checks if there are any optional classes that can be set as default factory"""

    for name, attribute in cls_obj.attributes.items():
        dtype = re.sub(r"\[|\]|Union|Optional", "", attribute["dtype"])

        if dtype not in classes:
            continue
        elif isinstance(classes[dtype], MermaidEnum):
            continue
        elif isinstance(classes[dtype], MermaidExternal):
            continue

        # Check if the datatype has only optional values
        is_optional = all(
            bool(re.match(r"List|Optional", attr["dtype"]))
            for attr in classes[dtype].attributes.values()
        )

        if is_optional:
            cls_obj.attributes[name]["default_factory"] = dtype
            del cls_obj.attributes[name]["default"]


def render_dunder_init(classes: dict, module_doc):
    """Renders the __init__ file of the module"""

    # Get the init template
    init_template = jinja2.Template(
        pkg_resources.read_text(jinja_templates, "init_file_template.jinja2")
    )

    return init_template.render(
        classes=sorted(classes.values(), key=lambda cls: cls.fname),
        docstring=module_doc.replace("/", "").replace('"', "'"),
    )

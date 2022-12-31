from copy import deepcopy
from typing import Dict, List, Optional
from jinja2 import Template
from importlib import resources as pkg_resources

from sdRDM.generator.datatypes import DataTypes
from sdRDM.generator import templates as jinja_templates

from .utils import camel_to_snake, clean_imports


def render_object(
    object: Dict, objects: List[Dict], enums: List[Dict], inherits: List[Dict]
) -> str:

    """Renders a class of type object coming from a parsed Markdown model"""

    all_objects = objects + enums

    # Get the class body
    class_part = render_class(object=object, inherits=inherits)
    methods_part = render_add_methods(object=object, objects=all_objects)
    class_body = class_part + "\n" + "\n\n".join(methods_part)

    # Clean and render imports
    imports = render_imports(object=object, objects=all_objects, inherits=inherits)
    imports = clean_imports(imports, class_body)

    return f"{imports}\n\n{class_body}"


def render_class(
    object: Dict,
    inherits: List[Dict],
    repo: Optional[str] = None,
    commit: Optional[str] = None,
) -> str:
    """Takes an object definition and returns a rendered string"""

    object = deepcopy(object)
    template = Template(
        pkg_resources.read_text(jinja_templates, "class_template.jinja2")
    )

    inherit = None

    filtered = list(
        filter(lambda element: element["child"] == object["name"], inherits)
    )

    if filtered and len(filtered) == 1:
        inherit = filtered[0]["parent"]

    return template.render(
        name=object.pop("name"),
        inherit=inherit,
        docstring=object.pop("docstring"),
        attributes=[render_attribute(attr) for attr in object["attributes"]],
        repo=repo,
        commit=commit,
    )


def render_attribute(attribute: Dict) -> str:
    """Renders an attributeibute to code using a Jinja2 template"""

    attribute = deepcopy(attribute)
    template = Template(
        pkg_resources.read_text(jinja_templates, "attribute_template.jinja2")
    )

    is_multiple = attribute.pop("multiple")

    if is_multiple:
        attribute["default_factory"] = "ListPlus"

    return template.render(
        name=attribute.pop("name"),
        required=attribute.pop("required"),
        dtype=combine_types(attribute.pop("type"), is_multiple),
        metadata=stringize_option_values(attribute),
    )


def combine_types(dtypes: List[str], is_multiple: bool) -> str:
    """Combines a list of types into a Union if more than one"""

    dtypes = [
        DataTypes[dtype].value[0] if dtype in DataTypes.__members__ else dtype
        for dtype in dtypes
    ]

    return encapsulate_type(dtypes, is_multiple)


def stringize_option_values(attribute: Dict):
    """Puts string type values in literals for code generation"""

    for key, option in attribute.items():
        if not isinstance(option, str) or option == "ListPlus":
            continue

        attribute[key] = f'"{option}"'

    return attribute


def render_add_methods(object: Dict, objects: List[Dict]) -> List[str]:
    """Renders add methods fro each non-native type of an attribute"""

    add_methods = []

    for attribute in object["attributes"]:
        for type in attribute["type"]:
            if is_enum_type(type, objects):
                continue
            elif type in DataTypes.__members__:
                continue

            add_methods.append(render_single_add_method(attribute, type, objects))

    return add_methods


def is_enum_type(name: str, objects: List[Dict]) -> bool:
    """Checks whether the given object is of type Enum"""

    try:
        obj = get_object(name, objects)
    except ValueError:
        return False

    return obj["type"] == "enum"


def render_single_add_method(attribute: Dict, type: str, objects: List[Dict]) -> str:
    """Renders an add method for an attribute that occurs multiple times"""

    attribute = deepcopy(attribute)
    objects = deepcopy(objects)

    template = Template(
        pkg_resources.read_text(jinja_templates, "add_method_template.jinja2")
    )

    return template.render(
        snake_case=camel_to_snake(attribute["name"]),
        attribute=attribute["name"],
        cls=type,
        type=camel_to_snake(type),
        signature=assemble_signature(type, objects),
        summary=f"This method adds an object of type '{type}' to attribute {attribute['name']}",
    )


def assemble_signature(type: str, objects: List[Dict]) -> List[Dict]:
    """Takes a non-native sdRDM type defined within the model and extracts all attributes"""

    try:
        sub_object_attrs = next(filter(lambda object: object["name"] == type, objects))[
            "attributes"
        ]
    except StopIteration:
        raise ValueError(f"Sub object '{type}' has no attributes.")

    list(map(convert_type, sub_object_attrs))
    sub_object_attrs.sort(
        key=lambda attr: (
            "default" in attr or attr["required"] is False or attr["multiple"] is True
        )
    )

    return sub_object_attrs


def convert_type(attribute: Dict) -> None:
    """Turns argument types into correct typings"""

    type = attribute["type"]

    union_type = [
        DataTypes[subtype].value[0] if subtype in DataTypes.__members__ else subtype
        for subtype in type
    ]

    attribute["type"] = encapsulate_type(union_type, attribute["multiple"])


def encapsulate_type(dtypes: List[str], is_multiple: bool) -> str:
    """Puts types if necessary within Union or List typing"""

    if len(dtypes) == 1:
        if is_multiple == True:
            return f"List[{dtypes[0]}]"
        else:
            return dtypes[0]
    else:
        if is_multiple == True:
            return f"List[Union[{', '.join(dtypes)}]]"
        else:
            return f"Union[{', '.join(dtypes)}]"


def render_imports(object: Dict, objects: List[Dict], inherits: List[Dict]) -> str:
    """Retrieves all necessary external and local imports for this class"""

    objects = deepcopy(objects)
    object = deepcopy(object)

    all_types = gather_all_types(object["attributes"], objects)

    for inherit in inherits:
        if inherit["child"] != object["name"]:
            continue

        parent_type = inherit["parent"]
        all_types += gather_all_types(
            get_object(parent_type, objects)["attributes"], objects
        )

    # Sort types into local and from imports
    all_types = list(set(all_types))
    external_imports = [
        DataTypes[type].value[1]
        for type in all_types
        if type in DataTypes.__members__ and DataTypes[type].value[1]
    ]

    local_imports = [
        f"from .{type.lower()} import {type}"
        for type in all_types
        if type not in DataTypes.__members__
    ]

    imports = [
        imp for imps in external_imports for imp in imps if not imp.startswith("from ")
    ]

    from_imports = [
        imp for imps in external_imports for imp in imps if imp.startswith("from ")
    ]

    template = Template(
        pkg_resources.read_text(jinja_templates, "import_template.jinja2")
    )

    return template.render(
        imports=imports, from_imports=from_imports, local_imports=local_imports
    )


def gather_all_types(attributes: List[Dict], objects: List[Dict]) -> List[str]:
    """Gets the occuring types in all attributes"""

    types = []

    for attribute in attributes:
        types += attribute["type"]

        if attribute["multiple"]:
            types += [
                subtype
                for nested_type in attribute["type"]
                for subtype in gather_all_types(
                    get_object(nested_type, objects)["attributes"], objects
                )
                if nested_type not in DataTypes.__members__
            ]

    return types


def get_object(name: str, objects: List[Dict]) -> Dict:
    """Returns object by its name"""

    try:
        return next(filter(lambda object: object["name"] == name, objects))
    except StopIteration:
        raise ValueError(f"Could not find object '{name}' in objects.")
from copy import deepcopy
from typing import Dict, List, Optional, Union, Tuple
from jinja2 import Template
from importlib import resources as pkg_resources

from sdRDM.generator.datatypes import DataTypes
from sdRDM.generator import templates as jinja_templates

from .utils import camel_to_snake, clean_imports


def render_object(
    object: Dict,
    objects: List[Dict],
    enums: List[Dict],
    inherits: List[Dict],
    repo: Optional[str] = None,
    commit: Optional[str] = None,
) -> str:
    """Renders a class of type object coming from a parsed Markdown model"""

    all_objects = objects + enums

    # Get the class body
    class_part = render_class(
        object=object, inherits=inherits, objects=all_objects, repo=repo, commit=commit
    )
    methods_part = render_add_methods(object=object, objects=all_objects)
    validator_part = render_reference_validator(object=object, objects=all_objects)
    class_body = "\n".join([class_part, methods_part, validator_part])

    # Clean and render imports
    imports = render_imports(object=object, objects=all_objects, inherits=inherits)
    # imports = clean_imports(imports, class_body)

    return f"{imports}\n\n{class_body}"


def render_class(
    object: Dict,
    inherits: List[Dict],
    objects: List[Dict],
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
        attributes=[render_attribute(attr, objects) for attr in object["attributes"]],
        repo=repo,
        commit=commit,
    )


def render_attribute(attribute: Dict, objects: List[Dict]) -> str:
    """Renders an attributeibute to code using a Jinja2 template"""

    attribute = deepcopy(attribute)
    template = Template(
        pkg_resources.read_text(jinja_templates, "attribute_template.jinja2")
    )

    is_multiple = "multiple" in attribute
    is_required = attribute["required"]
    has_reference = "reference" in attribute

    if is_multiple:
        attribute["default_factory"] = "ListPlus"

    if has_reference:
        reference_types = get_reference_type(attribute["reference"], objects)
        attribute["type"] += reference_types

    return template.render(
        name=attribute.pop("name"),
        required=attribute.pop("required"),
        dtype=combine_types(attribute.pop("type"), is_multiple, is_required),
        metadata=stringize_option_values(attribute),
    )


def combine_types(dtypes: List[str], is_multiple: bool, is_required: bool) -> str:
    """Combines a list of types into a Union if more than one"""

    dtypes = [
        DataTypes[dtype].value[0] if dtype in DataTypes.__members__ else dtype
        for dtype in dtypes
    ]

    return encapsulate_type(dtypes, is_multiple, is_required)


def get_reference_type(reference: str, objects: List[Dict]) -> List[str]:
    """Gets the type of a specific reference used for automatic fetching"""
    object, attribute = reference.split(".")

    if attribute == "id":
        return ["str"]

    assert any(
        object == obj["name"] for obj in objects
    ), f"Object '{object}' cannot be found in model for referencing."

    object = next(filter(lambda obj: obj["name"] == object, objects))

    assert any(
        attribute == attr["name"] for attr in object["attributes"]
    ), f"Attribute '{attribute}' cannot be found in model for referencing."

    return next(filter(lambda attr: attr["name"] == attribute, object["attributes"]))


def stringize_option_values(attribute: Dict):
    """Puts string type values in literals for code generation"""

    for key, option in attribute.items():
        if not is_pure_string_type(option) or option == "ListPlus":
            continue
        elif is_reference(key, option):
            continue

        attribute[key] = f'"{option}"'

    return attribute


def is_pure_string_type(value: str) -> Union[bool, str]:
    """Checks whether the given option value could be bool"""

    if value is None:
        return False
    elif value.lower() in ["true", "false"]:
        return False
    elif value.lower() == "false":
        return False

    try:
        int(value)
        float(value)
    except ValueError:
        return True

    return False


def is_reference(key: str, option: str) -> bool:
    """Checks whether this is a reference to another class -> Mainly used for Enums"""

    if key != "default":
        return False

    if len(option.split(".")) > 1 and option.count(" ") == 0:
        # Typically references to classes will follow pattern 'Something.something'
        return True

    return False


def render_add_methods(object: Dict, objects: List[Dict]) -> str:
    """Renders add methods fro each non-native type of an attribute"""

    add_methods = []

    for attribute in object["attributes"]:
        complex_types = get_complex_types(attribute, objects)
        is_single_type = len(complex_types) == 1

        for type in complex_types:
            add_methods.append(
                render_single_add_method(attribute, type, objects, is_single_type)
            )

    return "\n\n".join(add_methods)


def get_complex_types(attribute: Dict, objects: List[Dict]) -> List[str]:
    """Checks whether an attributes types contain multiple complex types"""

    complex_types = []

    for type in attribute["type"]:
        if is_enum_type(type, objects):
            continue
        elif type in DataTypes.__members__ or not "multiple" in attribute:
            continue

        complex_types.append(type)

    return complex_types


def render_reference_validator(object: Dict, objects: List[Dict]) -> str:
    """Renders refrence methods that are used to extract specified attributes from an object"""

    template = Template(
        pkg_resources.read_text(jinja_templates, "reference_template.jinja2")
    )

    validator_funcs = []
    attributes = deepcopy(
        list(filter(lambda attribute: "reference" in attribute, object["attributes"]))
    )

    for attribute in attributes:
        target_obj, target_attribute = attribute["reference"].split(".")

        assert any(
            target_obj == model_obj["name"] for model_obj in objects
        ), f"Target object {target_obj} not found in model."

        validator_func = template.render(
            attribute=attribute["name"],
            object=target_obj,
            target=target_attribute,
            types=get_reference_type(attribute["reference"], objects),
            required=attribute["required"],
        )

        validator_funcs.append(validator_func)

    return "\n\n".join(validator_funcs)


def is_enum_type(name: str, objects: List[Dict]) -> bool:
    """Checks whether the given object is of type Enum"""

    try:
        obj = get_object(name, objects)
    except ValueError:
        return False

    return obj["type"] == "enum"


def render_single_add_method(
    attribute: Dict, type: str, objects: List[Dict], is_single_type: bool
) -> str:
    """Renders an add method for an attribute that occurs multiple times"""

    attribute = deepcopy(attribute)
    objects = deepcopy(objects)

    template = Template(
        pkg_resources.read_text(jinja_templates, "add_method_template.jinja2")
    )

    # Generate the name of the method
    attr_name = camel_to_snake(attribute["name"])
    type_name = camel_to_snake(type)

    if attr_name == type_name or is_single_type:
        destination = f"to_{attr_name}"
    else:
        destination = f"{type_name}_to_{attr_name}"

    return template.render(
        attribute=attribute["name"],
        destination=destination,
        cls=type,
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

    sub_object_attrs = [convert_type(attribute) for attribute in sub_object_attrs]

    return sorted(sub_object_attrs, key=sort_by_defaults, reverse=True)


def sort_by_defaults(attribute: Dict) -> bool:
    """Sorting key function to put attributes with defaults last"""

    if "multiple" in attribute:
        return False
    elif attribute["required"] is False:
        return False
    elif "default" in attribute:
        return False
    elif "default_factors" in attribute:
        return False
    else:
        return True


def convert_type(attribute: Dict) -> Dict:
    """Turns argument types into correct typings"""

    type = attribute["type"]

    if attribute["required"] is False and "multiple" not in attribute:
        attribute["default"] = None
    elif "multiple" in attribute:
        attribute["default"] = "ListPlus()"

    union_type = [
        DataTypes[subtype].value[0] if subtype in DataTypes.__members__ else subtype
        for subtype in type
    ]

    attribute["type"] = encapsulate_type(
        union_type, bool("multiple" in attribute), attribute["required"]
    )

    return attribute


def encapsulate_type(dtypes: List[str], is_multiple: bool, is_required: bool) -> str:
    """Puts types if necessary within Union or List typing"""

    if len(dtypes) == 1:
        if is_multiple == True:
            return f"List[{dtypes[0]}]"
        elif is_required is False:
            return f"Optional[{dtypes[0]}]"
        else:
            return dtypes[0]
    else:
        if is_multiple == True:
            return f"List[Union[{', '.join(dtypes)}]]"
        elif is_required is False:
            return f"Union[{', '.join(dtypes)}, None]"
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
        ) + [parent_type]

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

        for nested_type in attribute["type"]:
            types += process_subtypes(nested_type, objects)

    return types


def get_object(name: str, objects: List[Dict]) -> Dict:
    """Returns object by its name"""

    try:
        return next(filter(lambda object: object["name"] == name, objects))
    except StopIteration:
        raise ValueError(f"Could not find object '{name}' in objects.")


def process_subtypes(nested_type: str, objects: List[Dict]) -> List[str]:
    """Processes types from nested attribute types"""

    types = []

    if nested_type in DataTypes.__members__:
        return []

    object = get_object(nested_type, objects)

    if object["type"] == "enum":
        return []

    attributes = object["attributes"]
    subtypes = gather_all_types(attributes, objects)

    for subtype in subtypes:
        types.append(subtype)

    return types
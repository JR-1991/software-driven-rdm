import re
import yaml


class YAMLDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(YAMLDumper, self).increase_indent(flow, False)


def snake_to_camel(word: str) -> str:

    if "_" not in word:
        return word[0].upper() + word[1::]

    return "".join(x.capitalize() or "_" for x in word.split("_"))


def camel_to_snake(name: str) -> str:
    name = re.sub("@", "", name)
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def check_numeric(value):
    # Checks whether the given value is of special type

    if value.lower() == "none":
        return value

    if value.lower() in ["false", "true"]:
        return value

    try:
        int(value)
        float(value)
        bool(value)
        return value
    except ValueError:
        return f'"{value}"'


def elem2dict(node):
    """
    Convert an lxml.etree node tree into a dict.

    Args:
        node (lxml.etree.Element): The lxml.etree node tree to be converted.

    Returns:
        dict: The converted dictionary representation of the node tree.
    """
    result = {}

    for element in node.iterchildren():
        key = element.tag.split("}")[1] if "}" in element.tag else element.tag
        if element.text and element.text.strip():
            value = element.text
        else:
            value = elem2dict(element)

        result[key] = value

    return result

import textwrap

from typing import Dict, Optional


class ImportedModules:
    """Empty class used to store all sub classes"""

    def __init__(
        self,
        classes,
        enums: Optional["ImportedModules"] = None,
        links: Optional[Dict] = None,
        include_links: bool = True,
    ):
        for name, node in classes.items():
            if hasattr(node, "cls"):
                # Add all classes
                setattr(self, name, node.cls)
            elif hasattr(node, "__fields__"):
                # Add classes that are not presented as a node
                setattr(self, name, node)
            elif isinstance(node, dict):
                # Add links if given
                setattr(self, name, node)

        if enums:
            self.enums = self.__class__(classes=enums, include_links=False)

        # Process links
        if include_links:
            self.links = links
            self._distribute_links()

    def _distribute_links(self):
        """Adds the given links as instance methods"""

        if self.links is None:
            return

        for name, link in self.links.items():
            obj = getattr(self, link["__model__"])
            converter = lambda self: self.convert_to(template=link)[0]
            setattr(obj, f"to_{name.replace(' ', '_')}", converter)

    def __repr__(self) -> str:

        GROUPS = ["Objects", "enums", "links"]
        MAXINDENT = len("Objects ")
        out_string = []

        for group in GROUPS:
            prefix = (
                f"\033[96m{group.capitalize()}\033[0m{' ' * (MAXINDENT - len(group))}"
            )
            wrapper = textwrap.TextWrapper(
                initial_indent=prefix, width=100, subsequent_indent="        "
            )

            if group not in self.__dict__:
                out_string += [
                    wrapper.fill(
                        ", ".join(
                            [name for name in self.__dict__ if name not in GROUPS]
                        )
                    )
                ]
            elif group == "enums":
                out_string += [
                    wrapper.fill(
                        ", ".join([name for name in getattr(self, group).__dict__])
                    )
                ]
            elif group == "links":
                out_string += [
                    wrapper.fill(", ".join([name for name in getattr(self, group)]))
                ]

        return "\n".join(out_string)

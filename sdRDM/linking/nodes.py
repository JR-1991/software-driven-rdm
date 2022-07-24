import importlib
import copy

from typing import List
from anytree import Node, LevelOrderGroupIter


class AttributeNode(Node):
    def __init__(self, name, parent=None, value=None, outer_type=None):
        super().__init__(name, parent)

        self.value = {}
        self.outer_type = outer_type


class ClassNode(Node):
    def __init__(
        self, name, parent=None, module=None, class_name=None, outer_type=None
    ):
        super().__init__(name, parent)

        self.module = module
        self.class_name = class_name
        self.outer_type = outer_type

    def import_class(self):
        """Imports the class that is described in this node"""
        module = importlib.import_module(self.module)
        return getattr(module, self.class_name)

    def instantiate(self):
        """Instantiates the class connected to this node"""

        cls = self.import_class()

        if all(node.value == {} for node in self.children):
            return {0: cls(**{node.name: None for node in self.children})}
        else:
            indices = self._get_unique_indices()
            return {index: cls(**self._get_kwargs(index=index)) for index in indices}

    def _get_kwargs(self, index=0):
        """Generates list of keyword arguments used to set up a sub class"""

        kwargs = {}
        for child in self.children:
            if index in child.value:
                value = child.value[index]
                kwargs[child.name] = value

        return kwargs

    def _get_unique_indices(self):
        """Gets all keys in a nodes value dictionary"""
        return {index for node in self.children for index in node.value.keys()}

    def build(self):
        """Instantiates all children that are present in this (sub-)tree and builds the data model.

        (1) Build a list of all levels present
        (2) Reverse the list and work from leaves to root
        (3) Instantiate each sub-class and add it to the parent root
        (4) Stop when the current node is reached

        Returns:
            sdRDM.DataModel: Instantiated tree of the data model
        """

        self_copy = copy.deepcopy(self)
        level_order = list(LevelOrderGroupIter(self_copy))[::-1]

        for level in level_order:
            if all(isinstance(node, AttributeNode) for node in level):
                continue

            for node in level:
                if node == self_copy:
                    # Stop the flow once the root node is reached
                    continue

                # Instantiate and get the parent
                cls = node.instantiate()
                parent = node.parent

                # Check if all sub classes are empty
                is_empty = all(
                    sub_cls.dict(exclude_none=True) == {} for sub_cls in cls.values()
                )

                if parent.outer_type.__name__ == "list":
                    # Check for list processing
                    if is_empty:
                        parent.value = {0: []}
                    else:
                        parent.value = {0: list(cls.values())}
                else:
                    if is_empty:
                        parent.value = {0: None}
                    else:
                        parent.value = {0: list(cls.values())[0]}

        return self_copy.instantiate()[0]
from abc import ABC, abstractmethod
from typing import List, Union

from sdRDM import DataModel


class Operation(
    DataModel,
    nsmap={"": "http://www.w3.org/1998/Math/MathML"},
):
    """
    Abstract base class for mathematical operations.
    """

    @abstractmethod
    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):  # type: ignore
        """
        Abstract method to convert the operation to a string representation.
        """
        pass


class NonOperation(
    DataModel,
    nsmap={"": "http://www.w3.org/1998/Math/MathML"},
):
    """
    Abstract base class representing a non-operation in the mathml module.
    """

    @abstractmethod
    def to_string(self):
        """
        Abstract method to convert the non-operation to a string representation.
        """
        pass

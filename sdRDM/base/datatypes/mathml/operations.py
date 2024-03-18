from typing import List, Optional, Union
from pydantic_xml import element
from pydantic import ConfigDict, ValidationError, constr, field_validator

from sdRDM.base.listplus import ListPlus

from .base import Operation, NonOperation


class plus(Operation, tag="plus"):
    """
    Represents the plus operation in mathml.

    Methods:
        to_string: Converts the plus operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        return " + ".join([part.to_string() for part in apply_])


class minus(Operation, tag="minus"):
    """
    Represents the subtraction operation in mathml.

    Methods:
        to_string: Converts the subtraction operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        return " - ".join([part.to_string() for part in apply_])


class times(Operation, tag="times"):
    """
    Represents the multiplication operation in MathML.

    Methods:
        to_string: Converts the multiplication operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        return "*".join([part.to_string() for part in apply_])


class divide(Operation, tag="divide"):
    """
    Represents the divide operation in mathml.

    Methods:
        to_string: Converts the divide operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        assert len(apply_) == 2, "divide should have two arguments"

        return f"{apply_[0].to_string()} / {apply_[1].to_string()}"


class power(Operation, tag="power"):
    """
    Represents the power operation in mathml.

    Methods:
        to_string: Converts the power operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        assert len(apply_) == 2, "power should have two arguments"

        return f"{apply_[0].to_string()}**{apply_[1].to_string()}"


class root(Operation, tag="root"):
    """
    Represents the square root operation in mathml.

    Methods:
        to_string: Converts the square root operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        assert len(apply_) == 2, "root should have two arguments"

        return f"{apply_[0].to_string()}**(1/{apply_[1].to_string()})"


class ln(Operation, tag="ln"):
    """
    Represents the natural logarithm operation.

    Methods:
        to_string: Converts the natural logarithm operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        assert len(apply_) == 1, "ln should only have one argument"

        return f"ln({apply_[0].to_string()})"


class exp(Operation, tag="exp"):
    """
    Represents the exponential operation.

    Methods:
        to_string: Converts the exponential operation to a string representation.
    """

    def to_string(self, apply_: List[Union["ci", "cn", "apply"]]):
        assert len(apply_) == 1, "exp should only have one argument"

        return f"exp({apply_[0].to_string()})"


class ci(NonOperation, tag="ci"):
    """
    Represents a ci element in MathML.

    Attributes:
        symbol (str): The symbol associated with the ci element.

    Methods:
        to_string: Returns the symbol associated with the ci element.
    """

    symbol: str = constr(strip_whitespace=True)  # type: ignore

    def __init__(self, symbol: str):
        super().__init__(symbol=symbol)

    def to_string(self):
        return self.symbol


class cn(NonOperation, tag="cn"):
    """
    Represents a cn element in MathML.

    Attributes:
        value (str): The value associated with the cn element.

    Methods:
        to_string: Returns the number associated with the cn element as a string.
    """

    value: Union[float, int] = constr(strip_whitespace=True)  # type: ignore

    def __init__(self, value: Union[float, int]):
        super().__init__(value=value)

    def to_string(self):
        return str(self.value)


class apply(NonOperation, tag="apply"):
    """
    Represents an apply element in MathML.

    Attributes:
        model_config (ConfigDict): Configuration dictionary for the model.
        operation (Union[plus, minus, ln, power, times, root, divide]): The operation to be applied.
        apply_ (List[Union[ci, cn, "apply"]]): List of apply elements.

    Methods:
        to_string(): Converts the apply element to a string representation.
        _extract_variables(): Extracts the variables from the apply element.

    """

    model_config: ConfigDict = ConfigDict(
        populate_by_name=True,
    )

    # Operations
    operation: Union[
        plus,
        minus,
        ln,
        power,
        times,
        root,
        divide,
    ]

    # Consumables
    apply_: List[Union[ci, cn, "apply"]] = element(
        default_factory=ListPlus,
        alias="apply",
    )

    @field_validator("operation", mode="before")
    @classmethod
    def _validate_apply(cls, value):
        if issubclass(type(value), Operation):
            return value

        raise ValidationError(
            f"operation must be a subclass of Operation, not {type(value)}"
        )

    def to_string(self):
        return f"{self.operation.to_string(self.apply_)}"

    def _extract_variables(self) -> List[str]:
        variables = []
        for part in self.apply_:
            if isinstance(part, ci):
                variables.append(part.symbol.strip())
            elif isinstance(part, apply):
                variables.extend(part._extract_variables())
        return variables

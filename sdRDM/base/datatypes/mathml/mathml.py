import re

from typing import List
from pydantic_xml import element
from pydantic import PrivateAttr, model_validator
from sympy import sympify

from sdRDM import DataModel

from sdRDM.base.datatypes.mathml.operations import apply


class math(
    DataModel,
    tag="math",
    nsmap={"": "http://www.w3.org/1998/Math/MathML"},
):
    """
    Represents a MathML object.

    Args:
        DataModel: Base class for data models.
        tag (str): The XML tag for the MathML object.
        nsmap (dict): The namespace map for the MathML object.

    Attributes:
        model_config (ConfigDict): Configuration dictionary for the MathML object.
        apply_ (apply): The apply element of the MathML object.
        _variables (List[str]): List of variables extracted from the MathML object.

    Methods:
        to_equation: Converts the MathML object to an equation string.
        _extract_variables: Extracts variables from the MathML object.
        from_equation: Creates a MathML object from an equation string.
    """

    apply_: apply = element(alias="apply", tag="apply")

    _variables: List[str] = PrivateAttr()

    def to_equation(self):
        """
        Converts the MathML object to an equation string.

        Returns:
            str: The equation string.
        """
        return self.apply_.to_string()

    def to_sympy(self):
        """
        Converts the MathML object to a sympy expression.

        Returns:
            sympy.Expr: The sympy expression.
        """
        return sympify(self.to_equation())

    def __call__(self, **kwargs):
        """
        Evaluates the MathML object.

        Args:
            **kwargs: Keyword arguments to be passed to the sympy expression.

        Returns:
            float: The result of the evaluation.
        """

        assert all(
            [var in kwargs for var in self._variables]
        ), "Not all variables are provided."

        assert all(
            [isinstance(kwargs[var], (int, float)) for var in self._variables]
        ), "Not all variables are numbers."

        return float(self.to_sympy().evalf(subs=kwargs))

    @model_validator(mode="after")
    def _extract_variables(self):
        """
        Extracts variables from the MathML object.
        """
        self._variables = list(set(self.apply_._extract_variables()))

        return self

    @classmethod
    def from_equation(cls, equation: str) -> "MathML":  # type: ignore
        """
        Creates a MathML object from an equation string.

        Args:
            equation (str): The equation string.

        Returns:
            MathML: The MathML object.
        """

        try:
            from sympy import sympify
            from sympy.printing.mathml import MathMLContentPrinter
        except ImportError:
            raise ImportError(
                "The sympy package is required to use the math module.",
                "Please install it using `pip install sdrdm[math]` or `pip install sympy`.",
            )

        printer = MathMLContentPrinter()
        xml = printer._print(
            sympify(equation),
        ).toprettyxml()  # type: ignore

        # Wrap in math tag, otherwise wont parse
        xml = f"""
        <math xmlns="http://www.w3.org/1998/Math/MathML">
            {cls._extract_subscriptions(xml)}
        </math>
        """

        return cls.from_xml_string(xml)

    @staticmethod
    def _extract_subscriptions(xml: str):
        """
        Extracts the subscriptions from the MathML object.
        """

        pattern = r"<mml:msub><mml:mi>([A-Za-z0-9]*)</mml:mi><mml:mi>([A-Za-z0-9]*)</mml:mi></mml:msub>"
        xml = re.sub(r"\s+", "", xml)

        return re.sub(pattern, r"\1_\2", xml)

    def __repr__(self) -> str:
        return self.to_equation()

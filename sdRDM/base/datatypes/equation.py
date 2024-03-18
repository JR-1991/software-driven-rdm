from pydantic_xml import computed_element
from sympy import sympify

from sdRDM import DataModel
from sdRDM.base.listplus import ListPlus


class Equation(DataModel):
    """
    Represents an equation.

    Args:
        DataModel: Base class for data models.

    Attributes:
        equation (str): The equation string.
    """

    equation: str

    def __init__(self, equation: str):
        super().__init__(equation=equation)

    @computed_element(tag="symbol", return_type=ListPlus[str])
    def symbols(self):
        """
        Returns a list of symbols present in the equation.

        Returns:
            ListPlus[str]: A list of symbols present in the equation.
        """
        eq = sympify(self.equation)
        return [str(symbol) for symbol in eq.free_symbols]

    def __call__(self, **kwargs):
        """
        Evaluates the Equation object.

        Args:
            **kwargs: Keyword arguments to be passed to the sympy expression.

        Returns:
            float: The result of the evaluation.
        """

        assert all(
            [var in kwargs for var in self.symbols]
        ), "Not all variables are provided."

        assert all(
            [isinstance(kwargs[var], (int, float)) for var in self.symbols]
        ), "Not all variables are numbers."

        return float(self.to_sympy().evalf(subs=kwargs))

    def to_sympy(self):
        """
        Converts the Equation object to a sympy expression.

        Returns:
            sympy.Expr: The sympy expression.
        """
        return sympify(self.equation)

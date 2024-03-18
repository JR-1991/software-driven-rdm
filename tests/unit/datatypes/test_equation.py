from sympy import sympify
from sdRDM.base.datatypes.equation import Equation


class TestEquation:
    def test_equation(self):
        eq = Equation("x + 2")

        assert eq.symbols == ["x"]
        assert eq(x=1) == 3.0
        assert eq.to_sympy() == sympify("x + 2")

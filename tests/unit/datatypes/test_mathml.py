from pydantic import ValidationError
import pytest
import re
from sympy import sympify

from sdRDM.base.datatypes.mathml import operations as ops
from sdRDM.base.datatypes.mathml import MathML


class TestMathML:
    def test_from_equation(self):
        mathml = MathML.from_equation("x + 2")

        expected = """
            <?xml version='1.0' encoding='UTF-8'?>
            <math xmlns="http://www.w3.org/1998/Math/MathML">
                <apply>
                    <plus/>
                    <ci>x</ci>
                    <cn>2.0</cn>
                </apply>
            </math>
        """

        assert re.sub(r"\s+", "", mathml.xml()) == re.sub(r"\s+", "", expected)
        assert mathml.to_equation() == "x + 2.0"

    def test_subscripted_equation(self):
        mathml = MathML.from_equation("x_1 + 2")

        expected = """
            <?xml version='1.0' encoding='UTF-8'?>
            <math xmlns="http://www.w3.org/1998/Math/MathML">
                <apply>
                    <plus/>
                    <ci>x_1</ci>
                    <cn>2.0</cn>
                </apply>
            </math>
        """

        assert re.sub(r"\s+", "", mathml.xml()) == re.sub(r"\s+", "", expected)
        assert mathml.to_equation() == "x_1 + 2.0"

    def test_to_sympy(self):
        mathml = MathML.from_equation("x + 2")

        assert mathml.to_sympy() == sympify("x + 2.0")


class TestOperations:

    @pytest.mark.unit
    def test_plus(self):
        assert ops.plus().to_string([ops.ci("x"), ops.cn("2")]) == "x + 2.0"

    @pytest.mark.unit
    def test_minus(self):
        assert ops.minus().to_string([ops.ci("x"), ops.cn("2")]) == "x - 2.0"

    @pytest.mark.unit
    def test_times(self):
        assert ops.times().to_string([ops.ci("x"), ops.cn("2")]) == "x*2.0"

    @pytest.mark.unit
    def test_divide(self):
        assert ops.divide().to_string([ops.ci("x"), ops.cn("2")]) == "x / 2.0"

    @pytest.mark.unit
    def test_divide_raises_error(self):
        with pytest.raises(AssertionError):
            ops.divide().to_string([ops.ci("x"), ops.cn("2"), ops.cn("3")])

    @pytest.mark.unit
    def test_power(self):
        assert ops.power().to_string([ops.ci("x"), ops.cn("2")]) == "x**2.0"

    @pytest.mark.unit
    def test_power_raises_error(self):
        with pytest.raises(AssertionError):
            ops.power().to_string([ops.ci("x"), ops.cn("2"), ops.cn("3")])

    @pytest.mark.unit
    def test_root(self):
        assert ops.root().to_string([ops.ci("x"), ops.cn("2")]) == "x**(1/2.0)"

    @pytest.mark.unit
    def test_root_raises_error(self):
        with pytest.raises(AssertionError):
            ops.root().to_string([ops.ci("x"), ops.cn("2"), ops.cn("3")])

    @pytest.mark.unit
    def test_exp(self):
        assert ops.exp().to_string([ops.ci("x")]) == "exp(x)"

    @pytest.mark.unit
    def test_exp_raises_error(self):
        with pytest.raises(AssertionError):
            ops.exp().to_string([ops.ci("x"), ops.cn("2")])

    @pytest.mark.unit
    def test_ln(self):
        assert ops.ln().to_string([ops.ci("x")]) == "ln(x)"

    @pytest.mark.unit
    def test_ln_raises_error(self):
        with pytest.raises(AssertionError):
            ops.ln().to_string([ops.ci("x"), ops.cn("2")])

    @pytest.mark.unit
    def test_ci(self):
        assert ops.ci("x").to_string() == "x"

    @pytest.mark.unit
    def test_cn(self):
        assert ops.cn("2").to_string() == "2.0"

    @pytest.mark.unit
    def test_apply(self):
        result = ops.apply(
            operation=ops.plus(),
            apply_=[ops.ci("x"), ops.cn("2")],
        )

        assert result.to_string() == "x + 2.0"

    @pytest.mark.unit
    def test_apply_raises_error(self):
        with pytest.raises(ValidationError):
            ops.apply(
                operation=ops.plus(),
                apply_=[ops.ci("x"), "2"],
            )

    @pytest.mark.unit
    def test_apply_extract_variables(self):
        apply = ops.apply(
            operation=ops.plus(),
            apply_=[ops.ci("x"), ops.cn("2")],
        )

        assert apply._extract_variables() == ["x"]

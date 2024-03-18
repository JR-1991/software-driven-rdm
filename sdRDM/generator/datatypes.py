from enum import Enum


class DataTypes(Enum):
    """Holds Data Type mappings"""

    string = ("str", None)
    str = ("str", None)
    float = ("float", None)
    int = ("int", None)
    integer = ("int", None)
    bytes = ("bytes", None)
    Unit = ("Unit", ["from sdRDM.base.datatypes import Unit"])
    unit = ("Unit", ["from sdRDM.base.datatypes import Unit"])
    EmailStr = ("EmailStr", ["from pydantic import EmailStr"])
    Email = ("EmailStr", ["from pydantic import EmailStr"])
    HttpUrl = ("HttpUrl", ["from pydantic import HttpUrl"])
    HttpURL = ("HttpUrl", ["from pydantic import HttpUrl"])
    httpurl = ("HttpUrl", ["from pydantic import HttpUrl"])
    AnyHttpUrl = ("AnyHttpUrl", ["from pydantic import AnyHttpUrl"])
    AnyHttpURL = ("AnyHttpUrl", ["from pydantic import AnyHttpUrl"])
    anyhttpurl = ("AnyHttpUrl", ["from pydantic import AnyHttpUrl"])
    AnyUrl = ("AnyUrl", ["from pydantic import AnyUrl"])
    URL = ("AnyUrl", ["from pydantic import AnyUrl"])
    posfloat = ("PositiveFloat", ["from pydantic import PositiveFloat"])
    PositiveFloat = ("PositiveFloat", ["from pydantic import PositiveFloat"])
    positivefloat = ("PositiveFloat", ["from pydantic import PositiveFloat"])
    date = ("Date", ["from datetime import date as Date"])
    datetime = ("Datetime", ["from datetime import datetime as Datetime"])
    bool = ("bool", None)
    boolean = ("bool", None)
    Decimal = ("Decimal", ["from pydantic.types import Decimal"])
    decimal = ("Decimal", ["from pydantic.types import Decimal"])
    Path = ("Path", ["from pydantic.types import Path"])
    path = ("Path", ["from pydantic.types import Path"])
    Any = ("Any", ["from typing import Any"])
    any = ("Any", ["from typing import Any"])
    Callable = ("Callable", ["from pydantic.types import Callable"])
    callable = ("Callable", ["from pydantic.types import Callable"])
    FrozenSet = ("FrozenSet", ["from pydantic.types import FrozenSet"])
    frozenset = ("FrozenSet", ["from pydantic.types import FrozenSet"])
    Pattern = ("Pattern", ["from pydantic.types import Pattern"])
    pattern = ("Pattern", ["from pydantic.types import Pattern"])
    UUID = ("UUID", ["from pydantic.types import UUID"])
    uuid = ("UUID", ["from pydantic.types import UUID"])
    NoneStr = ("NoneStr", ["from pydantic import NoneStr"])
    nonestr = ("NoneStr", ["from pydantic import NoneStr"])
    NoneBytes = ("NoneBytes", ["from pydantic import NoneBytes"])
    nonebytes = ("NoneBytes", ["from pydantic import NoneBytes"])
    StrBytes = ("StrBytes", ["from pydantic import StrBytes"])
    strbytes = ("StrBytes", ["from pydantic import StrBytes"])
    NoneStrBytes = ("NoneStrBytes", ["from pydantic import NoneStrBytes"])
    nonestrbytes = ("NoneStrBytes", ["from pydantic import NoneStrBytes"])
    StrIntFloat = ("StrIntFloat", ["from pydantic.types import StrIntFloat"])
    strintfloat = ("StrIntFloat", ["from pydantic.types import StrIntFloat"])
    StrictBool = ("StrictBool", ["from pydantic import StrictBool"])
    strictbool = ("StrictBool", ["from pydantic import StrictBool"])
    PositiveInt = ("PositiveInt", ["from pydantic import PositiveInt"])
    positiveint = ("PositiveInt", ["from pydantic import PositiveInt"])
    NegativeInt = ("NegativeInt", ["from pydantic import NegativeInt"])
    negativeint = ("NegativeInt", ["from pydantic import NegativeInt"])
    NonPositiveInt = ("NonPositiveInt", ["from pydantic import NonPositiveInt"])
    nonpositiveint = ("NonPositiveInt", ["from pydantic import NonPositiveInt"])
    NonNegativeInt = ("NonNegativeInt", ["from pydantic import NonNegativeInt"])
    nonnegativeint = ("NonNegativeInt", ["from pydantic import NonNegativeInt"])
    StrictInt = ("StrictInt", ["from pydantic import StrictInt"])
    strictint = ("StrictInt", ["from pydantic import StrictInt"])

    ConstrainedFloat = (
        "ConstrainedFloat",
        ["from pydantic import ConstrainedFloat"],
    )

    constrainedfloat = (
        "ConstrainedFloat",
        ["from pydantic import ConstrainedFloat"],
    )

    NegativeFloat = ("NegativeFloat", ["from pydantic import NegativeFloat"])
    negativefloat = ("NegativeFloat", ["from pydantic import NegativeFloat"])

    NonPositiveFloat = (
        "NonPositiveFloat",
        ["from pydantic import NonPositiveFloat"],
    )

    nonpositivefloat = (
        "NonPositiveFloat",
        ["from pydantic import NonPositiveFloat"],
    )

    NonNegativeFloat = (
        "NonNegativeFloat",
        ["from pydantic import NonNegativeFloat"],
    )

    nonnegativefloat = (
        "NonNegativeFloat",
        ["from pydantic import NonNegativeFloat"],
    )

    StrictFloat = ("StrictFloat", ["from pydantic import StrictFloat"])
    strictfloat = ("StrictFloat", ["from pydantic import StrictFloat"])
    StrictBytes = ("StrictBytes", ["from pydantic import StrictBytes"])
    strictbytes = ("StrictBytes", ["from pydantic import StrictBytes"])
    StrictStr = ("StrictStr", ["from pydantic import StrictStr"])
    strictstr = ("StrictStr", ["from pydantic import StrictStr"])
    UUID1 = ("UUID1", ["from pydantic import UUID1"])
    uuid1 = ("UUID1", ["from pydantic import UUID1"])
    UUID3 = ("UUID3", ["from pydantic import UUID3"])
    uuid3 = ("UUID3", ["from pydantic import UUID3"])
    UUID4 = ("UUID4", ["from pydantic import UUID4"])
    uuid4 = ("UUID4", ["from pydantic import UUID4"])
    UUID5 = ("UUID5", ["from pydantic import UUID5"])
    uuid5 = ("UUID5", ["from pydantic import UUID5"])
    FilePath = ("FilePath", ["from pydantic import FilePath"])
    filepath = ("FilePath", ["from pydantic import FilePath"])
    DirectoryPath = ("DirectoryPath", ["from pydantic import DirectoryPath"])
    directorypath = ("DirectoryPath", ["from pydantic import DirectoryPath"])
    Json = ("Json", ["from pydantic import Json"])
    json = ("Json", ["from pydantic import Json"])
    PastDate = ("PastDate", ["from pydantic import PastDate"])
    pastdate = ("PastDate", ["from pydantic import PastDate"])
    FutureDate = ("FutureDate", ["from pydantic import FutureDate"])
    futuredate = ("FutureDate", ["from pydantic import FutureDate"])

    NDArray = (
        "Union[NDArray, H5Dataset]",
        [
            "from numpy.typing import NDArray",
            "from h5py._hl.dataset import Dataset as H5Dataset",
            "from typing import Union",
        ],
    )

    ndarray = (
        "Union[NDArray, H5Dataset]",
        [
            "from numpy.typing import NDArray",
            "from h5py._hl.dataset import Dataset as H5Dataset",
            "from typing import Union",
        ],
    )

    ndArray = (
        "Union[NDArray, H5Dataset]",
        [
            "from numpy.typing import NDArray",
            "from h5py._hl.dataset import Dataset as H5Dataset",
            "from typing import Union",
        ],
    )

    H5Dataset = ("H5Dataset", ["from h5py._hl.dataset import Dataset as H5Dataset"])
    h5dataset = ("H5Dataset", ["from h5py._hl.dataset import Dataset as H5Dataset"])
    MathML = ("MathML", ["from sdRDM.base.datatypes import MathML"])
    Equation = ("Equation", ["from sdRDM.base.datatypes import Equation"])
    RawXML = ("_Element", ["from lxml.etree import _Element"])

    @classmethod
    def get_value_list(cls):
        return [member.value[0] for member in cls]

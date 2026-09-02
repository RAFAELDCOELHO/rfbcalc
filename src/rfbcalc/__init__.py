"""Python client for the official RFB CBS/IBS / Imposto Seletivo calculator.

This project is an unofficial client. It is NOT the Receita Federal and implements
no tax rule of its own: every rate, base and value comes from the official motor.
See the disclaimer in the README.
"""

from .client import OFFLINE_BASE_URL, ONLINE_BASE_URL, Calculator, RfbCalcError
from .models import (
    BaseCalculoCibsInput,
    BaseCalculoIsInput,
    BaseCalculoOutput,
    CompraGovernamentalInput,
    ImpostoSeletivoInput,
    ItemOperacaoInput,
    OperacaoInput,
    RegimeGeralOutput,
    Versao,
)

__version__ = "0.1.0"

__all__ = [
    "Calculator",
    "RfbCalcError",
    "ONLINE_BASE_URL",
    "OFFLINE_BASE_URL",
    "BaseCalculoCibsInput",
    "BaseCalculoIsInput",
    "BaseCalculoOutput",
    "CompraGovernamentalInput",
    "ImpostoSeletivoInput",
    "ItemOperacaoInput",
    "OperacaoInput",
    "RegimeGeralOutput",
    "Versao",
    "__version__",
]

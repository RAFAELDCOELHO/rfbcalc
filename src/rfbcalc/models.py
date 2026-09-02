"""Typed request/response models for the official RFB consumption-tax calculator.

Field names mirror the official API verbatim (camelCase, Portuguese) so that every
attribute can be cross-referenced against the official OpenAPI document at
https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/api/api-docs

No tax rule, rate or base is implemented here. These are transport types only:
the official motor computes everything.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # extra="allow" keeps forward compatibility: the official motor is under active
    # development (VERSAO BETA) and may add fields at any time. Dropping them silently
    # would hide official output from the caller.
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# --------------------------------------------------------------------------
# POST /calculadora/base-calculo/cbs-ibs-mercadorias
# --------------------------------------------------------------------------
class BaseCalculoCibsInput(_Base):
    """Inputs for the CBS/IBS calculation base for goods."""

    anoFatoGerador: int = Field(description="Ano do fato gerador")
    valorBem: Decimal | None = None
    ajusteAcrescimos: Decimal | None = None
    juros: Decimal | None = None
    multas: Decimal | None = None
    encargos: Decimal | None = None
    frete: Decimal | None = None
    impostoSeletivo: Decimal | None = None
    outrosTributos: Decimal | None = None
    demaisImportancias: Decimal | None = None
    icms: Decimal | None = None
    iss: Decimal | None = None
    pis: Decimal | None = None
    pisImportacao: Decimal | None = None
    cofins: Decimal | None = None
    cofinsImportacao: Decimal | None = None
    cosip: Decimal | None = None
    ipi: Decimal | None = None
    descontoIncondicional: Decimal | None = None


# --------------------------------------------------------------------------
# POST /calculadora/base-calculo/is-mercadorias
# --------------------------------------------------------------------------
class BaseCalculoIsInput(_Base):
    """Inputs for the Imposto Seletivo calculation base for goods."""

    anoFatoGerador: int = Field(description="Ano do fato gerador")
    valorBem: Decimal | None = None
    ajusteAcrescimos: Decimal | None = None
    juros: Decimal | None = None
    multas: Decimal | None = None
    encargos: Decimal | None = None
    freteCobrado: Decimal | None = None
    outrosTributos: Decimal | None = None
    demaisImportancias: Decimal | None = None
    icms: Decimal | None = None
    iss: Decimal | None = None
    cosip: Decimal | None = None
    ipi: Decimal | None = None
    descontoIncondicional: Decimal | None = None
    bonificacao: Decimal | None = None
    devolucaoVendas: Decimal | None = None


class BaseCalculoOutput(_Base):
    """Calculation base returned by the official motor."""

    baseCalculo: Decimal


# --------------------------------------------------------------------------
# POST /calculadora/regime-geral
# --------------------------------------------------------------------------
class CompraGovernamentalInput(_Base):
    tpEnteGov: int
    tpOperGov: int


class ImpostoSeletivoInput(_Base):
    cst: str
    cClassTrib: str
    baseCalculo: Decimal
    impostoInformado: Decimal
    quantidade: Decimal | None = None
    unidade: str | None = None


class TributacaoRegularInput(_Base):
    """Tributação regular applicable to a differentiated/benefited item."""

    cst: str
    cClassTrib: str


class ItemOperacaoInput(_Base):
    numero: int
    cst: str
    cClassTrib: str
    ncm: str | None = None
    nbs: str | None = None
    baseCalculo: Decimal | None = None
    quantidade: Decimal | None = None
    unidade: str | None = None
    impostoSeletivo: ImpostoSeletivoInput | None = None
    tributacaoRegular: TributacaoRegularInput | None = None


class OperacaoInput(_Base):
    """A consumption operation submitted to the regime-geral endpoint."""

    id: str
    versao: str
    municipio: int
    itens: list[ItemOperacaoInput]
    dhFatoGerador: str | None = None
    dataHoraEmissao: str | None = None
    uf: str | None = None
    gCompraGov: CompraGovernamentalInput | None = None


# --- regime-geral output -------------------------------------------------
# The official response carries the full DFe tax structure. The nodes below are
# the totals every caller needs; `extra="allow"` preserves the rest verbatim, so
# nothing the motor returns is lost. Reach for `.model_extra` or `.raw` for the
# untouched payload.
class ImpostoSeletivoTotal(_Base):
    vIS: Decimal | None = None


class IBSUFTotal(_Base):
    vIBSUF: Decimal | None = None
    vDif: Decimal | None = None
    vDevTrib: Decimal | None = None


class IBSMunTotal(_Base):
    vIBSMun: Decimal | None = None
    vDif: Decimal | None = None
    vDevTrib: Decimal | None = None


class IBSTotal(_Base):
    vIBS: Decimal | None = None
    gIBSUF: IBSUFTotal | None = None
    gIBSMun: IBSMunTotal | None = None
    vCredPres: Decimal | None = None
    vCredPresCondSus: Decimal | None = None


class CBSTotal(_Base):
    vCBS: Decimal | None = None
    vDif: Decimal | None = None
    vDevTrib: Decimal | None = None
    vCredPres: Decimal | None = None
    vCredPresCondSus: Decimal | None = None


class IBSCBSTotal(_Base):
    vBCIBSCBS: Decimal | None = None
    gIBS: IBSTotal | None = None
    gCBS: CBSTotal | None = None


class TributosTotais(_Base):
    IBSCBSTot: IBSCBSTotal | None = None
    ISTot: ImpostoSeletivoTotal | None = None


class ValoresTotais(_Base):
    tribCalc: TributosTotais | None = None


class RegimeGeralOutput(_Base):
    """Official regime-geral result.

    `objetos` and `oper` are kept as raw mappings: they mirror the DFe layout and
    are passed through untouched rather than partially re-typed.
    """

    total: ValoresTotais | None = None
    objetos: list[dict[str, object]] | None = None
    oper: dict[str, object] | None = None

    @property
    def vCBS(self) -> Decimal | None:
        """Total CBS, exactly as returned by the official motor."""
        tot = self._ibscbs_total()
        return tot.gCBS.vCBS if tot and tot.gCBS else None

    @property
    def vIBS(self) -> Decimal | None:
        """Total IBS (UF + municipal), exactly as returned by the official motor."""
        tot = self._ibscbs_total()
        return tot.gIBS.vIBS if tot and tot.gIBS else None

    @property
    def vBC(self) -> Decimal | None:
        """Total CBS/IBS calculation base, as returned by the official motor."""
        tot = self._ibscbs_total()
        return tot.vBCIBSCBS if tot else None

    @property
    def vIS(self) -> Decimal | None:
        """Total Imposto Seletivo, as returned by the official motor."""
        if self.total and self.total.tribCalc and self.total.tribCalc.ISTot:
            return self.total.tribCalc.ISTot.vIS
        return None

    def _ibscbs_total(self) -> IBSCBSTotal | None:
        if self.total and self.total.tribCalc:
            return self.total.tribCalc.IBSCBSTot
        return None


class Versao(_Base):
    """Version of the official motor and of its reference database."""

    versaoApp: str | None = None
    versaoDb: str | None = None
    descricaoVersaoDb: str | None = None
    dataVersaoDb: str | None = None
    ambiente: str | None = None

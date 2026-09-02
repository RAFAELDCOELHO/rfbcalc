"""HTTP client for the official RFB CBS/IBS/Imposto Seletivo calculator.

This module only transports JSON to and from the official motor. It never computes,
rounds or infers a tax value, a rate or a calculation base.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import TracebackType
from typing import Any

import httpx

from .models import (
    BaseCalculoCibsInput,
    BaseCalculoIsInput,
    BaseCalculoOutput,
    OperacaoInput,
    RegimeGeralOutput,
    Versao,
)

#: Official online motor (Receita Federal "piloto CBS" environment).
ONLINE_BASE_URL = "https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/api"

#: Default address the official offline calculator listens on once started.
OFFLINE_BASE_URL = "http://localhost:8080/api"

__all__ = ["Calculator", "RfbCalcError", "ONLINE_BASE_URL", "OFFLINE_BASE_URL"]


class RfbCalcError(RuntimeError):
    """An error returned by the official motor (RFC 7807 problem+json)."""

    def __init__(self, status_code: int, problem: dict[str, Any], url: str) -> None:
        self.status_code = status_code
        self.problem = problem
        self.url = url
        title = problem.get("title") or "erro"
        detail = problem.get("detail") or ""
        super().__init__(f"[HTTP {status_code}] {title}: {detail}".rstrip(": "))


class Calculator:
    """Client for the official Receita Federal consumption-tax calculator.

    >>> with Calculator() as calc:                            # doctest: +SKIP
    ...     calc.base_calculo_cbs_ibs(anoFatoGerador=2026, valorBem=1000, icms=180)

    Use :meth:`offline` to point at a locally running official motor instead.
    """

    def __init__(
        self,
        base_url: str = ONLINE_BASE_URL,
        *,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    @classmethod
    def offline(cls, base_url: str = OFFLINE_BASE_URL, **kwargs: Any) -> Calculator:
        """Talk to the official *offline* calculator running on this machine.

        Download it from the official site and start it (Java 21 or Docker); it
        serves the same API as the online motor on http://localhost:8080/api.
        See the README section "Offline motor".
        """
        return cls(base_url, **kwargs)

    # -- transport --------------------------------------------------------
    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        response = self._client.post(url, json=payload)
        return self._decode(response, url)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        response = self._client.get(url, params=params)
        return self._decode(response, url)

    @staticmethod
    def _decode(response: httpx.Response, url: str) -> Any:
        # parse_float=Decimal keeps monetary values exact: the motor is the source of
        # truth down to the centavo and a float round-trip can move the last digit.
        try:
            body = json.loads(response.text, parse_float=Decimal)
        except ValueError:
            body = None
        if response.is_error:
            problem = body if isinstance(body, dict) else {"detail": response.text}
            raise RfbCalcError(response.status_code, problem, url)
        return body

    # -- official endpoints ----------------------------------------------
    def base_calculo_cbs_ibs(self, **campos: Any) -> BaseCalculoOutput:
        """CBS/IBS calculation base for goods.

        ``POST /calculadora/base-calculo/cbs-ibs-mercadorias``
        """
        payload = BaseCalculoCibsInput(**campos)
        body = self._post(
            "/calculadora/base-calculo/cbs-ibs-mercadorias",
            # exclude_none: omitted amounts are not sent, so the motor applies its own defaults
            payload.model_dump(mode="json", exclude_none=True),
        )
        return BaseCalculoOutput.model_validate(body)

    def base_calculo_imposto_seletivo(self, **campos: Any) -> BaseCalculoOutput:
        """Imposto Seletivo calculation base for goods.

        ``POST /calculadora/base-calculo/is-mercadorias``
        """
        payload = BaseCalculoIsInput(**campos)
        body = self._post(
            "/calculadora/base-calculo/is-mercadorias",
            # exclude_none: omitted amounts are not sent, so the motor applies its own defaults
            payload.model_dump(mode="json", exclude_none=True),
        )
        return BaseCalculoOutput.model_validate(body)

    def regime_geral(self, operacao: OperacaoInput | dict[str, Any]) -> RegimeGeralOutput:
        """Full CBS/IBS/IS calculation for a consumption operation.

        ``POST /calculadora/regime-geral``
        """
        if isinstance(operacao, dict):
            operacao = OperacaoInput.model_validate(operacao)
        body = self._post(
            "/calculadora/regime-geral",
            operacao.model_dump(mode="json", exclude_none=True),
        )
        return RegimeGeralOutput.model_validate(body)

    def versao(self) -> Versao:
        """Version of the official motor and its reference database.

        ``GET /calculadora/dados-abertos/versao``
        """
        return Versao.model_validate(self._get("/calculadora/dados-abertos/versao"))

    # -- lifecycle --------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Calculator:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

"""Live checks against the real official RFB motor.

Deselected by default (see `addopts` in pyproject.toml) so CI never depends on a
government service being up. Run them with:  make test-live
"""

import pytest

from rfbcalc import Calculator

pytestmark = pytest.mark.live


def test_live_motor_matches_the_recorded_fixture():
    from rfbcalc.demo import main

    assert main([]) == 0


def test_live_versao():
    with Calculator() as calc:
        versao = calc.versao()
    assert versao.versaoApp
    assert versao.versaoDb


def test_live_rejects_invalid_cst():
    from rfbcalc import RfbCalcError

    with Calculator() as calc:
        with pytest.raises(RfbCalcError) as excinfo:
            calc.regime_geral(
                {
                    "id": "rfbcalc-live-invalid",
                    "versao": "1.0.0",
                    "dhFatoGerador": "2026-01-15T10:00:00-03:00",
                    "municipio": 3550308,
                    "itens": [
                        {"numero": 1, "cst": "999", "cClassTrib": "999999", "baseCalculo": "100.00"}
                    ],
                }
            )
    assert excinfo.value.status_code in (400, 404, 422)

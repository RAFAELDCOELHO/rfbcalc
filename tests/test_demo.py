"""The demo is the project's guarantee that we match the official motor.

These tests check the guarantee itself: that a mismatch is actually detected and
reported, and that the fixture is a genuine recording rather than a hand-written number.
"""

import json
from decimal import Decimal

import httpx
import pytest
import respx

from rfbcalc import demo
from rfbcalc.client import ONLINE_BASE_URL


def _routes(router: respx.Router, cases: dict, overrides: dict | None = None) -> None:
    overrides = overrides or {}
    router.get("/calculadora/dados-abertos/versao").mock(
        return_value=httpx.Response(200, json={"versaoApp": "1.3.1", "versaoDb": "V0043"})
    )
    for name, case in cases.items():
        body = overrides.get(name, case["response"])
        router.post(case["endpoint"]).mock(return_value=httpx.Response(200, json=body))


def test_demo_passes_when_motor_matches_the_recording(cases, capsys):
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        _routes(router, cases)
        assert demo.main([]) == 0
    assert "matches the recorded official result" in capsys.readouterr().out


def test_demo_fails_when_motor_is_off_by_one_centavo(cases, capsys):
    """One centavo of drift must fail the demo - that is the whole point."""
    drifted = dict(cases["base_calculo_cbs_ibs"]["response"])
    drifted["baseCalculo"] = str(Decimal(drifted["baseCalculo"]) + Decimal("0.01"))
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        _routes(router, cases, overrides={"base_calculo_cbs_ibs": drifted})
        assert demo.main([]) == 1
    err = capsys.readouterr().err
    assert "MISMATCH" in err
    assert "base_calculo_cbs_ibs.baseCalculo" in err


def test_demo_reports_unreachable_motor(capsys):
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.get("/calculadora/dados-abertos/versao").mock(
            side_effect=httpx.ConnectError("refused")
        )
        assert demo.main([]) == 1
    assert "could not reach the official motor" in capsys.readouterr().err


def test_demo_offline_flag_targets_the_local_motor(capsys):
    with respx.mock(base_url="http://localhost:8080/api") as router:
        router.get("/calculadora/dados-abertos/versao").mock(
            side_effect=httpx.ConnectError("refused")
        )
        assert demo.main(["--offline"]) == 1
    assert "localhost:8080" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["base_calculo_cbs_ibs", "base_calculo_is", "regime_geral"])
def test_fixture_records_provenance(official, name):
    """Every expected number must be traceable to a recorded official response."""
    case = official["cases"][name]
    assert case["endpoint"].startswith("/calculadora/")
    assert case["request"] and case["response"]
    assert official["source"].startswith("https://piloto-cbs.tributos.gov.br/")
    assert official["motor_version"]["versaoApp"]
    assert official["motor_version"]["versaoDb"]
    assert official["recorded_at"]


def test_fixture_amounts_are_exact_decimals(official):
    """No float artefacts may creep into the ground truth."""
    raw = json.dumps(official["cases"], default=str)
    assert "0000000001" not in raw and "9999999" not in raw
    base = official["cases"]["base_calculo_cbs_ibs"]["response"]["baseCalculo"]
    assert Decimal(str(base)) == Decimal(str(base)).quantize(Decimal("0.01"))

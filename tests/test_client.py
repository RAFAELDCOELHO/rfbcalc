"""Client tests. These replay the RECORDED official responses through respx.

They verify the client's transport, typing and decimal handling. They deliberately do
not assert any tax rule: the expected numbers come from the official motor, never from
a calculation performed here.
"""

import json
from decimal import Decimal

import httpx
import pytest
import respx

from rfbcalc import Calculator, OperacaoInput, RfbCalcError
from rfbcalc.client import ONLINE_BASE_URL


def _mock(route_path: str, case: dict) -> respx.Router:
    router = respx.mock(base_url=ONLINE_BASE_URL, assert_all_called=False)
    router.post(route_path).mock(return_value=httpx.Response(200, json=case["response"]))
    return router


def test_base_calculo_cbs_ibs_returns_official_value(cases):
    case = cases["base_calculo_cbs_ibs"]
    with _mock(case["endpoint"], case):
        with Calculator() as calc:
            result = calc.base_calculo_cbs_ibs(**case["request"])
    assert result.baseCalculo == Decimal(case["response"]["baseCalculo"])
    assert isinstance(result.baseCalculo, Decimal)


def test_base_calculo_is_returns_official_value(cases):
    case = cases["base_calculo_is"]
    with _mock(case["endpoint"], case):
        with Calculator() as calc:
            result = calc.base_calculo_imposto_seletivo(**case["request"])
    assert result.baseCalculo == Decimal(case["response"]["baseCalculo"])


def test_regime_geral_exposes_official_totals(cases):
    case = cases["regime_geral"]
    expected = case["response"]["total"]["tribCalc"]["IBSCBSTot"]
    with _mock(case["endpoint"], case):
        with Calculator() as calc:
            result = calc.regime_geral(case["request"])
    assert result.vBC == Decimal(expected["vBCIBSCBS"])
    assert result.vIBS == Decimal(expected["gIBS"]["vIBS"])
    assert result.vCBS == Decimal(expected["gCBS"]["vCBS"])


def test_regime_geral_accepts_typed_input(cases):
    case = cases["regime_geral"]
    operacao = OperacaoInput.model_validate(case["request"])
    with _mock(case["endpoint"], case):
        with Calculator() as calc:
            result = calc.regime_geral(operacao)
    assert result.vCBS is not None


def test_request_payload_uses_official_field_names(cases):
    """The wire payload must be exactly what the official API documents."""
    case = cases["base_calculo_cbs_ibs"]
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        route = router.post(case["endpoint"]).mock(
            return_value=httpx.Response(200, json=case["response"])
        )
        with Calculator() as calc:
            calc.base_calculo_cbs_ibs(**case["request"])
    sent = json.loads(route.calls[0].request.content)
    assert set(sent) == set(case["request"])
    assert Decimal(str(sent["valorBem"])) == Decimal(str(case["request"]["valorBem"]))


def test_unset_optional_fields_are_not_sent():
    """Omitted amounts must not be coerced to zero - the motor applies its own defaults."""
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        route = router.post("/calculadora/base-calculo/cbs-ibs-mercadorias").mock(
            return_value=httpx.Response(200, json={"baseCalculo": "10.00"})
        )
        with Calculator() as calc:
            calc.base_calculo_cbs_ibs(anoFatoGerador=2026, valorBem="10.00")
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"anoFatoGerador": 2026, "valorBem": "10.00"}


def test_decimal_precision_is_not_lost_through_float():
    """A value a float cannot represent must survive the round trip exactly."""
    tricky = "0.145"
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.post("/calculadora/base-calculo/cbs-ibs-mercadorias").mock(
            return_value=httpx.Response(
                200,
                content=f'{{"baseCalculo": {tricky}}}',
                headers={"content-type": "application/json"},
            )
        )
        with Calculator() as calc:
            result = calc.base_calculo_cbs_ibs(anoFatoGerador=2026, valorBem="1.00")
    assert result.baseCalculo == Decimal(tricky)


def test_official_error_is_raised_with_problem_details():
    problem = {
        "type": "https://piloto-cbs.tributos.gov.br/errors/situacao-tributaria-nao-encontrada",
        "title": "Situação tributária não encontrada",
        "status": 404,
        "detail": "Situação tributária (CST) não encontrada para código 999",
    }
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.post("/calculadora/regime-geral").mock(
            return_value=httpx.Response(404, json=problem)
        )
        with Calculator() as calc:
            with pytest.raises(RfbCalcError) as excinfo:
                calc.regime_geral(
                    {
                        "id": "x",
                        "versao": "1.0.0",
                        "municipio": 3550308,
                        "itens": [{"numero": 1, "cst": "999", "cClassTrib": "999999"}],
                    }
                )
    assert excinfo.value.status_code == 404
    assert excinfo.value.problem["title"] == problem["title"]
    assert "Situação tributária" in str(excinfo.value)


def test_extra_fields_from_the_motor_are_preserved():
    """The motor is beta; new fields must reach the caller, not be dropped."""
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.post("/calculadora/base-calculo/cbs-ibs-mercadorias").mock(
            return_value=httpx.Response(200, json={"baseCalculo": "1.00", "campoNovo": "abc"})
        )
        with Calculator() as calc:
            result = calc.base_calculo_cbs_ibs(anoFatoGerador=2026, valorBem="1.00")
    assert result.model_extra == {"campoNovo": "abc"}


def test_offline_targets_the_local_official_motor():
    calc = Calculator.offline()
    assert calc.base_url == "http://localhost:8080/api"
    calc.close()


def test_versao_is_typed():
    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.get("/calculadora/dados-abertos/versao").mock(
            return_value=httpx.Response(200, json={"versaoApp": "1.3.1", "versaoDb": "V0043"})
        )
        with Calculator() as calc:
            versao = calc.versao()
    assert versao.versaoApp == "1.3.1"
    assert versao.versaoDb == "V0043"


# --- CLI -----------------------------------------------------------------
def test_cli_reports_missing_required_field_without_a_traceback(capsys):
    from rfbcalc.cli import main

    assert main(["base-calculo-cbs-ibs", "valorBem=100"]) == 2
    assert "anoFatoGerador" in capsys.readouterr().err


def test_cli_rejects_malformed_pair(capsys):
    from rfbcalc.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["base-calculo-cbs-ibs", "valorBem"])
    assert excinfo.value.code == 2
    assert "campo=valor" in capsys.readouterr().err


def test_cli_surfaces_official_error(cases, capsys):
    from rfbcalc.cli import main

    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.post("/calculadora/base-calculo/cbs-ibs-mercadorias").mock(
            return_value=httpx.Response(
                400, json={"title": "Campo inválido", "detail": "ano deve ser 2026 ou superior"}
            )
        )
        assert main(["base-calculo-cbs-ibs", "anoFatoGerador=1800", "valorBem=100"]) == 1
    assert "ano deve ser 2026 ou superior" in capsys.readouterr().err


def test_cli_prints_official_result(cases, capsys):
    from rfbcalc.cli import main

    case = cases["base_calculo_cbs_ibs"]
    with _mock(case["endpoint"], case):
        assert main(["base-calculo-cbs-ibs", "anoFatoGerador=2026", "valorBem=1000.00"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert Decimal(printed["baseCalculo"]) == Decimal(case["response"]["baseCalculo"])


def test_cli_reads_regime_geral_payload_from_stdin(cases, monkeypatch, capsys):
    import io

    from rfbcalc.cli import main

    case = cases["regime_geral"]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(case["request"])))
    with _mock(case["endpoint"], case):
        assert main(["regime-geral", "-"]) == 0
    printed = json.loads(capsys.readouterr().out)
    expected = case["response"]["total"]["tribCalc"]["IBSCBSTot"]["gCBS"]["vCBS"]
    assert Decimal(printed["total"]["tribCalc"]["IBSCBSTot"]["gCBS"]["vCBS"]) == Decimal(expected)


def test_cli_rejects_invalid_json_without_a_traceback(tmp_path, capsys):
    from rfbcalc.cli import main

    bad = tmp_path / "op.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["regime-geral", str(bad)]) == 2
    assert "JSON invalido" in capsys.readouterr().err


def test_cli_reports_unreachable_motor(capsys):
    from rfbcalc.cli import main

    with respx.mock(base_url=ONLINE_BASE_URL) as router:
        router.get("/calculadora/dados-abertos/versao").mock(
            side_effect=httpx.ConnectError("refused")
        )
        assert main(["versao"]) == 1
    assert "erro ao acessar o motor oficial" in capsys.readouterr().err


def test_version_is_single_sourced():
    from importlib.metadata import version

    import rfbcalc

    assert rfbcalc.__version__ == version("rfbcalc")

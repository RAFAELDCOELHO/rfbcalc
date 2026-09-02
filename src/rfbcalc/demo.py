"""`make demo`: calls the official RFB motor live and checks it against a recorded result.

The expected numbers are NOT written by hand. They live in
``src/rfbcalc/fixtures/official_responses.json``, recorded verbatim from the official motor
(see ``make record-fixtures``). The demo replays the same inputs against the live motor
and fails if any value moves by even one centavo.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from .client import ONLINE_BASE_URL, Calculator, RfbCalcError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "official_responses.json"

CENTAVO = Decimal("0.01")


def _centavos(value: Any) -> Decimal:
    """Round to the centavo for comparison. Never used to produce a tax value."""
    return Decimal(str(value)).quantize(CENTAVO)


def load_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh, parse_float=Decimal)
    return data


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    base_url = ONLINE_BASE_URL
    if "--offline" in argv:
        from .client import OFFLINE_BASE_URL

        base_url = OFFLINE_BASE_URL
    for arg in argv:
        if arg.startswith("--base-url="):
            base_url = arg.split("=", 1)[1]

    fixture = load_fixture()
    recorded = fixture["cases"]

    print("rfbcalc demo - official RFB CBS/IBS/IS calculator")
    print(f"  motor .......... {base_url}")
    print(f"  fixture ........ {FIXTURE.name} (recorded {fixture['recorded_at']})")
    rec_v = fixture["motor_version"]
    print(f"  recorded with .. app {rec_v.get('versaoApp')} / db {rec_v.get('versaoDb')}")

    try:
        with Calculator(base_url) as calc:
            live = calc.versao()
            print(f"  live motor ..... app {live.versaoApp} / db {live.versaoDb}")
            if live.versaoDb != rec_v.get("versaoDb"):
                print(
                    f"\n  NOTE: live reference DB ({live.versaoDb}) differs from the recorded"
                    f" one ({rec_v.get('versaoDb')}). Official values may legitimately have"
                    " changed; re-record with `make record-fixtures`."
                )
            print()

            failures: list[str] = []

            # --- CBS/IBS calculation base ---------------------------------
            case = recorded["base_calculo_cbs_ibs"]
            got = calc.base_calculo_cbs_ibs(**case["request"])
            want = _centavos(case["response"]["baseCalculo"])
            have = _centavos(got.baseCalculo)
            print("Base de calculo CBS/IBS (mercadorias)")
            for key, value in case["request"].items():
                print(f"    {key:<24} {value}")
            print(f"    {'=> baseCalculo':<24} R$ {have}")
            failures += _check("base_calculo_cbs_ibs.baseCalculo", want, have)

            # --- Imposto Seletivo calculation base ------------------------
            case = recorded["base_calculo_is"]
            got = calc.base_calculo_imposto_seletivo(**case["request"])
            want = _centavos(case["response"]["baseCalculo"])
            have = _centavos(got.baseCalculo)
            print("\nBase de calculo Imposto Seletivo (mercadorias)")
            print(f"    {'=> baseCalculo':<24} R$ {have}")
            failures += _check("base_calculo_is.baseCalculo", want, have)

            # --- regime geral ---------------------------------------------
            case = recorded["regime_geral"]
            result = calc.regime_geral(case["request"])
            expected_total = case["response"]["total"]["tribCalc"]["IBSCBSTot"]
            print("\nRegime geral (municipio 3550308 - Sao Paulo/SP)")
            print(f"    {'=> vBC (base)':<24} R$ {_centavos(result.vBC)}")
            print(f"    {'=> vIBS':<24} R$ {_centavos(result.vIBS)}")
            print(f"    {'=> vCBS':<24} R$ {_centavos(result.vCBS)}")
            failures += _check(
                "regime_geral.vBCIBSCBS",
                _centavos(expected_total["vBCIBSCBS"]),
                _centavos(result.vBC),
            )
            failures += _check(
                "regime_geral.vIBS",
                _centavos(expected_total["gIBS"]["vIBS"]),
                _centavos(result.vIBS),
            )
            failures += _check(
                "regime_geral.vCBS",
                _centavos(expected_total["gCBS"]["vCBS"]),
                _centavos(result.vCBS),
            )

            # --- regime geral: the Receita's own published example payload ---
            case = recorded["regime_geral_exemplo_oficial"]
            result = calc.regime_geral(case["request"])
            expected = case["response"]["total"]["tribCalc"]
            print("\nRegime geral - exemplo publicado pela propria Receita")
            print("    (scripts-python-exemplo.zip / input/entrada-regime-geral.json)")
            print(f"    {'=> vBC (base)':<24} R$ {_centavos(result.vBC)}")
            print(f"    {'=> vIBS':<24} R$ {_centavos(result.vIBS)}")
            print(f"    {'=> vCBS':<24} R$ {_centavos(result.vCBS)}")
            print(f"    {'=> vIS':<24} R$ {_centavos(result.vIS)}")
            failures += _check(
                "regime_geral_exemplo_oficial.vBCIBSCBS",
                _centavos(expected["IBSCBSTot"]["vBCIBSCBS"]),
                _centavos(result.vBC),
            )
            failures += _check(
                "regime_geral_exemplo_oficial.vIS",
                _centavos(expected["ISTot"]["vIS"]),
                _centavos(result.vIS),
            )
    except RfbCalcError as exc:
        print(f"\nFAIL: official motor rejected the request: {exc}", file=sys.stderr)
        return 1
    except (httpx.HTTPError, OSError) as exc:
        print(f"\nFAIL: could not reach the official motor at {base_url}: {exc}", file=sys.stderr)
        return 1

    print()
    if failures:
        for line in failures:
            print(f"MISMATCH: {line}", file=sys.stderr)
        print(
            f"\nFAIL: {len(failures)} value(s) differ from the recorded official result.",
            file=sys.stderr,
        )
        return 1

    print("OK: every value matches the recorded official result to the centavo.")
    return 0


def _check(label: str, want: Decimal, have: Decimal) -> list[str]:
    return [] if want == have else [f"{label}: expected {want}, motor returned {have}"]


if __name__ == "__main__":
    raise SystemExit(main())

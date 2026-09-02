#!/usr/bin/env python3
"""Record official RFB motor responses verbatim into the demo/test fixture.

Run with `make record-fixtures`. The fixture is the demo's ground truth, so it must
only ever be produced by this script talking to the official motor - never edited by
hand and never computed locally.

Amounts are sent as decimal strings (the motor accepts them and returns identical
results) so no float ever touches a monetary value.
"""

from __future__ import annotations

import argparse
import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from rfbcalc.client import ONLINE_BASE_URL

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "rfbcalc"
    / "fixtures"
    / ("official_responses.json")
)

# Public, synthetic fixtures. Values are arbitrary inputs; every RESULT comes from
# the official motor.
CASES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "base_calculo_cbs_ibs",
        "/calculadora/base-calculo/cbs-ibs-mercadorias",
        {
            "anoFatoGerador": 2026,
            "valorBem": "1000.00",
            "icms": "180.00",
            "pis": "16.50",
            "cofins": "76.00",
            "frete": "50.00",
            "descontoIncondicional": "30.00",
        },
    ),
    (
        "base_calculo_is",
        "/calculadora/base-calculo/is-mercadorias",
        {
            "anoFatoGerador": 2027,
            "valorBem": "1000.00",
            "icms": "180.00",
            "freteCobrado": "50.00",
            "descontoIncondicional": "30.00",
        },
    ),
    (
        "regime_geral",
        "/calculadora/regime-geral",
        {
            "id": "rfbcalc-demo-001",
            "versao": "1.0.0",
            "dhFatoGerador": "2026-01-15T10:00:00-03:00",
            "municipio": 3550308,
            "itens": [
                {
                    "numero": 1,
                    "cst": "000",
                    "cClassTrib": "000001",
                    "baseCalculo": "1000.00",
                    "quantidade": "1",
                    "unidade": "UN",
                }
            ],
        },
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=ONLINE_BASE_URL)
    ap.add_argument("--out", type=Path, default=FIXTURE)
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    with httpx.Client(timeout=60.0) as http:
        version = http.get(f"{base}/calculadora/dados-abertos/versao")
        version.raise_for_status()

        cases: dict[str, Any] = {}
        for name, path, payload in CASES:
            resp = http.post(f"{base}{path}", json=payload)
            resp.raise_for_status()
            cases[name] = {
                "endpoint": path,
                "request": payload,
                # parse_float=Decimal so recorded amounts stay exact on re-serialisation
                "response": json.loads(resp.text, parse_float=Decimal),
            }
            print(f"[ok] {name} -> {path}")

    doc = {
        "_README": (
            "Recorded verbatim from the official RFB motor. DO NOT EDIT BY HAND. "
            "Regenerate with: make record-fixtures"
        ),
        "recorded_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source": base,
        "motor_version": version.json(),
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, default=str)
        fh.write("\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

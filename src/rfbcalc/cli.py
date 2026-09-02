"""Command line interface for the official RFB consumption-tax calculator.

Amount arguments are given as ``campo=valor`` using the official field names, so what
you type maps one-to-one onto the official API payload:

    rfbcalc base-calculo-cbs-ibs anoFatoGerador=2026 valorBem=1000 icms=180
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import ValidationError

from . import __version__
from .client import OFFLINE_BASE_URL, ONLINE_BASE_URL, Calculator, RfbCalcError


def _usage(message: str) -> SystemExit:
    """Exit code 2 for bad user input, matching argparse's convention."""
    print(f"erro: {message}", file=sys.stderr)
    return SystemExit(2)


def _parse_campos(pairs: list[str]) -> dict[str, Any]:
    campos: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise _usage(f"esperado 'campo=valor', recebido {pair!r}")
        key, raw = pair.split("=", 1)
        key = key.strip()
        try:
            campos[key] = int(raw) if key == "anoFatoGerador" else Decimal(raw)
        except (ValueError, InvalidOperation) as exc:
            raise _usage(f"valor invalido para {key!r}: {raw!r}") from exc
    return campos


def _load_json(source: str) -> Any:
    text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    return json.loads(text, parse_float=Decimal)


def _dump(model: Any) -> None:
    print(
        json.dumps(model.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rfbcalc",
        description=(
            "Cliente nao-oficial da calculadora oficial da RFB (CBS/IBS/Imposto Seletivo). "
            "Todos os valores sao calculados pelo motor oficial."
        ),
    )
    parser.add_argument("--version", action="version", version=f"rfbcalc {__version__}")
    parser.add_argument(
        "--base-url", default=None, help=f"URL do motor oficial (padrao: {ONLINE_BASE_URL})"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=f"usa o motor oficial offline local ({OFFLINE_BASE_URL})",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="timeout HTTP em segundos")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("base-calculo-cbs-ibs", help="base de calculo de CBS/IBS (mercadorias)")
    p.add_argument("campos", nargs="*", metavar="campo=valor")
    p.add_argument("--json", dest="json_file", help="payload JSON completo ('-' para stdin)")

    p = sub.add_parser("base-calculo-is", help="base de calculo do Imposto Seletivo (mercadorias)")
    p.add_argument("campos", nargs="*", metavar="campo=valor")
    p.add_argument("--json", dest="json_file", help="payload JSON completo ('-' para stdin)")

    p = sub.add_parser("regime-geral", help="calculo completo de uma operacao de consumo")
    p.add_argument("json_file", metavar="OPERACAO.json", help="payload JSON ('-' para stdin)")

    sub.add_parser("versao", help="versao do motor oficial e da base de referencia")
    sub.add_parser("demo", help="roda a demonstracao contra o motor oficial")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "demo":
        from .demo import main as demo_main

        extra = []
        if args.offline:
            extra.append("--offline")
        if args.base_url:
            extra.append(f"--base-url={args.base_url}")
        return demo_main(extra)

    base_url = args.base_url or (OFFLINE_BASE_URL if args.offline else ONLINE_BASE_URL)

    try:
        with Calculator(base_url, timeout=args.timeout) as calc:
            if args.command == "versao":
                _dump(calc.versao())
            elif args.command == "regime-geral":
                _dump(calc.regime_geral(_load_json(args.json_file)))
            else:
                campos = (
                    _load_json(args.json_file) if args.json_file else _parse_campos(args.campos)
                )
                if args.command == "base-calculo-cbs-ibs":
                    _dump(calc.base_calculo_cbs_ibs(**campos))
                else:
                    _dump(calc.base_calculo_imposto_seletivo(**campos))
    except RfbCalcError as exc:
        print(f"erro do motor oficial: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        # Bad user input: report it plainly instead of dumping a traceback.
        for err in exc.errors():
            campo = ".".join(str(p) for p in err["loc"]) or "(payload)"
            print(f"erro: campo {campo}: {err['msg']}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"erro: JSON invalido: {exc}", file=sys.stderr)
        return 2
    except (httpx.HTTPError, OSError) as exc:
        print(f"erro ao acessar o motor oficial em {base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

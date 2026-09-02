# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Added
- `py.typed`: o pacote agora anuncia seus tipos para mypy/pyright.
- CI roda em Python 3.11 a 3.14; workflow de release para o PyPI via trusted publishing (tag `v*`).
- Dependabot para GitHub Actions e pip.

### Changed
- Versão com fonte única em `rfbcalc.__version__` (hatch `dynamic`).

## [0.1.0] - 2026-09-02

### Added
- Cliente tipado (Pydantic v2, `Decimal`) para os endpoints oficiais
  `base-calculo/cbs-ibs-mercadorias`, `base-calculo/is-mercadorias`,
  `regime-geral` e `dados-abertos/versao`.
- CLI `rfbcalc` com códigos de saída `0/1/2`.
- `make demo`: compara o motor oficial ao vivo com o fixture gravado, até o centavo.
- Suporte ao motor oficial offline (`Calculator.offline()`, `make demo-offline`).

[Unreleased]: https://github.com/RAFAELDCOELHO/rfbcalc/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RAFAELDCOELHO/rfbcalc/releases/tag/v0.1.0

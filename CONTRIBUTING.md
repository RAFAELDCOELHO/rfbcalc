# Contribuindo

Obrigado pelo interesse. Regras curtas:

1. **Nenhuma regra tributária em Python.** O projeto só transporta dados para o motor
   oficial da Receita Federal. PRs que calculem alíquota, base ou tributo localmente
   não serão aceitos, por mais simples que pareçam.
2. **Nomes de campo verbatim.** Os modelos espelham a API oficial (camelCase em
   português). Não renomeie campos "para ficar mais pythônico".
3. **Números esperados vêm do motor.** Nunca edite
   `src/rfbcalc/fixtures/official_responses.json` à mão; use `make record-fixtures`.
4. **`make check` verde** antes de abrir o PR (ruff, mypy strict, pytest sem rede).
   `make test-live` opcional, contra o motor oficial.
5. **Bugs do motor oficial** não são bugs deste projeto: reporte à Receita pelo canal
   da calculadora e, se quiser, abra uma issue aqui só para documentar o comportamento.

Para publicar uma versão: bump em `src/rfbcalc/__init__.py`, entrada no `CHANGELOG.md`,
tag `vX.Y.Z` e push. O workflow de release cuida do PyPI e do GitHub Release.

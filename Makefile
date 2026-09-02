# rfbcalc - Python client for the official RFB CBS/IBS/Imposto Seletivo calculator.
# `make demo` is the entry point: it sets everything up and talks to the official motor.

PY      ?= python3
VENV    := .venv
BIN     := $(VENV)/bin
MOTOR   := offline-motor
DL_API  := https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/api/calculadora/download/url?platform=default

.DEFAULT_GOAL := demo
.PHONY: demo demo-offline install test test-live lint typecheck check record-fixtures \
        offline-motor offline-start offline-stop build clean help

$(BIN)/python:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --quiet --upgrade pip

install: $(BIN)/python              ## install the package with dev extras
	$(BIN)/python -m pip install --quiet -e '.[dev]'

demo: install                       ## run the official calculation and check it to the centavo
	$(BIN)/python -m rfbcalc.demo

test: install                       ## unit tests (no network, official responses replayed)
	$(BIN)/python -m pytest -q

test-live: install                  ## tests that hit the real official motor
	$(BIN)/python -m pytest -q -m live

lint: install
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

typecheck: install
	$(BIN)/mypy

check: lint typecheck test           ## everything CI runs

record-fixtures: install            ## re-record the ground truth from the official motor
	$(BIN)/python scripts/record_fixtures.py

build: install
	$(BIN)/python -m pip install --quiet build
	$(BIN)/python -m build

# --- official offline motor -------------------------------------------------
# Downloads the official offline calculator and runs it locally. Requires Java 21+.
# The offline motor serves the same API as the online one, on port 8080.
$(MOTOR)/.ready:
	@mkdir -p $(MOTOR)
	@echo ">> resolving official download URL"
	@curl -fsSL "$(DL_API)" -o $(MOTOR)/url.json
	@echo ">> downloading the official offline calculator (large file, please wait)"
	@curl -fSL "$$($(PY) -c 'import json;print(json.load(open("$(MOTOR)/url.json"))["downloadUrl"])')" \
		-o $(MOTOR)/calculadora.zip
	@echo ">> unpacking"
	@cd $(MOTOR) && mkdir -p app && cd app && unzip -oq ../calculadora.zip
	@touch $@

offline-motor: $(MOTOR)/.ready      ## download + unpack the official offline calculator

offline-start: offline-motor        ## start the official offline motor on :8080
	@JAR="$$(find $(MOTOR)/app -name 'api-regime-geral.jar' | head -1)"; \
	if [ -z "$$JAR" ]; then \
	  echo "api-regime-geral.jar not found under $(MOTOR)/app."; \
	  echo "See the Docker route in the README (README.md, 'Motor offline')."; exit 1; fi; \
	command -v java >/dev/null || { echo "Java 21+ is required; see README."; exit 1; }; \
	echo ">> starting $$JAR (official command: java -jar ... --spring.profiles.active=offline)"; \
	java -jar "$$JAR" --spring.profiles.active=offline > $(MOTOR)/motor.log 2>&1 & \
	echo $$! > $(MOTOR)/motor.pid; \
	echo ">> waiting for http://localhost:8080/api"; \
	for i in $$(seq 1 120); do \
	  curl -fsS http://localhost:8080/api/calculadora/dados-abertos/versao >/dev/null 2>&1 && \
	    { echo ">> motor up"; exit 0; }; \
	  sleep 2; \
	done; \
	echo "motor did not come up; see $(MOTOR)/motor.log"; exit 1

offline-stop:                       ## stop the local offline motor
	@if [ -f $(MOTOR)/motor.pid ]; then kill "$$(cat $(MOTOR)/motor.pid)" 2>/dev/null; \
	  unlink $(MOTOR)/motor.pid; echo ">> stopped"; else echo ">> not running"; fi

demo-offline: install offline-start  ## same demo, against the official OFFLINE motor
	@$(BIN)/python -m rfbcalc.demo --offline; status=$$?; \
	 $(MAKE) --no-print-directory offline-stop; exit $$status

clean:                              ## delete build artefacts and the virtualenv
	$(PY) -c "import shutil,glob,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['$(VENV)','build','dist','.pytest_cache','.mypy_cache','.ruff_cache'] + glob.glob('**/*.egg-info', recursive=True) + [str(q) for q in pathlib.Path('.').rglob('__pycache__')]]"

help:                               ## list targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

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
# The official offline package (calculadora.zip) contains calculadora.tar.gz - a
# container image - plus the Receita's own install scripts. There is no loose .jar
# to run, so we follow the official Docker route:
#     docker import ./calculadora.tar.gz calculadora-image
#     docker run ... -w /calculadora calculadora-image bash start.sh
# (see linux/1-instalar.sh and linux/2-executar.sh inside the official package).
# We publish only 8080 (the API) and 8081; the official script also maps port 80 for
# the web portal, which needs privileges we do not want to require for the demo.
$(MOTOR)/.ready:
	@mkdir -p $(MOTOR)
	@echo ">> resolving the official download URL"
	@curl -fsSL "$(DL_API)" -o $(MOTOR)/url.json
	@echo ">> downloading the official offline calculator (~250 MB, this takes a while)"
	@curl -fSL "$$($(PY) -c 'import json;print(json.load(open("$(MOTOR)/url.json"))["downloadUrl"])')" \
		-o $(MOTOR)/calculadora.zip
	@echo ">> unpacking"
	@cd $(MOTOR) && unzip -oq calculadora.zip calculadora.tar.gz
	@touch $@

offline-motor: $(MOTOR)/.ready      ## download + unpack the official offline calculator

offline-start: offline-motor        ## start the official offline motor on :8080
	@docker info >/dev/null 2>&1 || { \
	  echo "Docker is required for the official offline calculator and is not running."; \
	  echo "See README.md section 'Motor offline'."; exit 1; }
	@docker image inspect calculadora-image >/dev/null 2>&1 || { \
	  echo ">> importing the official image (docker import)"; \
	  docker import $(MOTOR)/calculadora.tar.gz calculadora-image; }
	@docker rm -f calculadora-container >/dev/null 2>&1 || true
	@echo ">> starting the official offline motor"
	@docker run -d --rm -p 8080:8080 -p 8081:8081 -w /calculadora \
		--name calculadora-container calculadora-image bash start.sh >/dev/null
	@echo ">> waiting for http://localhost:8080/api"
	@for i in $$(seq 1 150); do \
	  curl -fsS http://localhost:8080/api/calculadora/dados-abertos/versao >/dev/null 2>&1 && \
	    { echo ">> motor up"; exit 0; }; \
	  sleep 2; \
	done; \
	echo "motor did not come up; logs: docker logs calculadora-container"; exit 1

offline-stop:                       ## stop the local offline motor
	@docker rm -f calculadora-container >/dev/null 2>&1 && echo ">> stopped" || echo ">> not running"

demo-offline: install offline-start  ## same demo, against the official OFFLINE motor
	@$(BIN)/python -m rfbcalc.demo --offline; status=$$?; \
	 $(MAKE) --no-print-directory offline-stop; exit $$status

clean:                              ## delete build artefacts and the virtualenv
	$(PY) -c "import shutil,glob,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['$(VENV)','build','dist','.pytest_cache','.mypy_cache','.ruff_cache'] + glob.glob('**/*.egg-info', recursive=True) + [str(q) for q in pathlib.Path('.').rglob('__pycache__')]]"

help:                               ## list targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

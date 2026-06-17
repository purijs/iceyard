.PHONY: api-install api-dev api-test api-lint api-format web-install web-dev web-build web-typecheck docker-up docker-down

PYTHON ?= python3.12
API_DIR := apps/api
WEB_DIR := apps/web

api-install:
	cd $(API_DIR) && $(PYTHON) -m pip install -e ".[dev]"

api-dev:
	cd $(API_DIR) && $(PYTHON) -m uvicorn iceyard_api.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd $(API_DIR) && $(PYTHON) -m pytest

api-lint:
	cd $(API_DIR) && $(PYTHON) -m ruff check iceyard_api

api-format:
	cd $(API_DIR) && $(PYTHON) -m ruff format iceyard_api

web-install:
	cd $(WEB_DIR) && npm install

web-dev:
	cd $(WEB_DIR) && npm run dev

web-build:
	cd $(WEB_DIR) && npm run build

web-typecheck:
	cd $(WEB_DIR) && npm run typecheck

docker-up:
	docker compose up --build

docker-down:
	docker compose down

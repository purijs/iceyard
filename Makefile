.PHONY: api-install api-env api-secret-key api-dev api-test api-lint api-format web-install web-dev web-build web-typecheck docker-up docker-down

PYTHON ?= python3.12
API_DIR := apps/api
WEB_DIR := apps/web
API_ENV := $(API_DIR)/.env

api-install:
	cd $(API_DIR) && $(PYTHON) -m pip install -e ".[dev]"

api-env:
	@if [ ! -f "$(API_ENV)" ]; then cp .env.example "$(API_ENV)"; fi
	@$(MAKE) api-secret-key

api-secret-key:
	@mkdir -p "$(API_DIR)"
	@if [ ! -f "$(API_ENV)" ]; then touch "$(API_ENV)"; fi
	@KEY="$$(cd $(API_DIR) && $(PYTHON) -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"; \
	if grep -q '^ICEYARD_SECRET_ENCRYPTION_KEY=' "$(API_ENV)"; then \
		sed -i.bak "s|^ICEYARD_SECRET_ENCRYPTION_KEY=.*|ICEYARD_SECRET_ENCRYPTION_KEY=$$KEY|" "$(API_ENV)" && rm -f "$(API_ENV).bak"; \
	elif grep -q '^# ICEYARD_SECRET_ENCRYPTION_KEY=' "$(API_ENV)"; then \
		sed -i.bak "s|^# ICEYARD_SECRET_ENCRYPTION_KEY=.*|ICEYARD_SECRET_ENCRYPTION_KEY=$$KEY|" "$(API_ENV)" && rm -f "$(API_ENV).bak"; \
	else \
		printf '\nICEYARD_SECRET_ENCRYPTION_KEY=%s\n' "$$KEY" >> "$(API_ENV)"; \
	fi
	@echo "Wrote ICEYARD_SECRET_ENCRYPTION_KEY to $(API_ENV)"

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

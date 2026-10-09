# SOVEREIGN — Makefile
# Common dev/CI entry points. Idempotent. Safe to call from any subdirectory.

.PHONY: help install dev test lint typecheck format migrate migrate-new clean run health

PYTHON ?= python3
UV    ?= uv

help:
	@echo "SOVEREIGN Makefile targets:"
	@echo "  make install      - install runtime + dev deps via uv"
	@echo "  make dev          - install + run the API in dev mode"
	@echo "  make run          - run the API (uvicorn)"
	@echo "  make test         - run the full test suite"
	@echo "  make unit         - run only unit tests"
	@echo "  make integration  - run only integration tests"
	@echo "  make lint         - ruff check"
	@echo "  make typecheck    - mypy strict"
	@echo "  make format       - ruff format"
	@echo "  make migrate      - apply alembic migrations to HEAD"
	@echo "  make migrate-new  - create a new alembic revision (NAME=...)"
	@echo "  make audit        - pip-audit security scan"
	@echo "  make clean        - remove caches + dev artifacts"

install:
	$(UV) pip install -e ".[dev]"

dev: install migrate run

run:
	$(PYTHON) -m uvicorn sovereign.api.app:app \
		--host $${SOVEREIGN_HOST:-127.0.0.1} \
		--port $${SOVEREIGN_PORT:-8000} \
		--reload

test:
	$(PYTHON) -m pytest -v

unit:
	$(PYTHON) -m pytest tests/unit -v

integration:
	$(PYTHON) -m pytest tests/integration -v -m integration

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy sovereign

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

migrate:
	$(PYTHON) -m alembic upgrade head

migrate-new:
	@test -n "$(NAME)" || (echo "Usage: make migrate-new NAME=baseline" && exit 1)
	$(PYTHON) -m alembic revision --autogenerate -m "$(NAME)"

audit:
	$(PYTHON) -m pip_audit --strict

health:
	@curl -sf http://127.0.0.1:8000/healthz && echo "" || (echo "API not reachable"; exit 1)

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
	rm -f sovereign.db

PYTHON ?= python3

.PHONY: check test lint typecheck

check: lint typecheck test

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy

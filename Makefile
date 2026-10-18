.DEFAULT_GOAL := check
PYTHON ?= python3

check:
	@$(PYTHON) tests/test_verify_reduction.py
	@$(PYTHON) tests/test_verify_cli.py
	@$(PYTHON) tests/test_integrations.py

assets:
	@$(PYTHON) assets/build.py

asset-check:
	@$(PYTHON) assets/build.py --check

.PHONY: check assets asset-check

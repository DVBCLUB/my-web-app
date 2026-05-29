.PHONY: help audit audit-strict preflight test smoke install-dev

help:
	@echo "FT ERP maintenance commands"
	@echo "  make audit        - scan large files and large Python modules"
	@echo "  make audit-strict - fail if unexpected oversized files/modules appear"
	@echo "  make preflight    - run audit-strict and smoke tests"
	@echo "  make test         - run pytest from repository root"
	@echo "  make smoke        - run minimal smoke tests only"
	@echo "  make install-dev  - install development/test requirements"

audit:
	python tools/repo_audit.py

audit-strict:
	python tools/repo_audit.py --fail-on-large

preflight:
	python tools/preflight.py

test:
	pytest

smoke:
	pytest PythonApplication1/tests/test_smoke_app.py

install-dev:
	python -m pip install -r PythonApplication1/requirements-dev.txt

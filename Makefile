.PHONY: help audit test smoke install-dev

help:
	@echo "FT ERP maintenance commands"
	@echo "  make audit       - scan large files and large Python modules"
	@echo "  make test        - run pytest from repository root"
	@echo "  make smoke       - run minimal smoke tests only"
	@echo "  make install-dev - install development/test requirements"

audit:
	python tools/repo_audit.py

test:
	pytest

smoke:
	pytest PythonApplication1/tests/test_smoke_app.py

install-dev:
	python -m pip install -r PythonApplication1/requirements-dev.txt

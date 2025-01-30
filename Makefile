# Configuration:
# Only set these if they have not been defined via command-line
# such as: make VENV_NAME=my_custom_venv
VENV_NAME ?= venv
PYTHON ?= python3
PYPIRC = $(HOME)/.pypirc

# Extract PROJECT_NAME from setup.py using helper script
PROJECT_NAME := $(shell $(PYTHON) get_project_name.py)
PROJECT_NAME_UNDERSCORE := $(subst -,_,$(PROJECT_NAME))

# Default target
.DEFAULT_GOAL := test-publish

# exclude special targets that start with a dot (like .PHONY)
# exclude pattern rules that use % (like %.o: %.c)
show-make-targets:
	@grep -E '^[^.%].*[^ ]:' Makefile | cut -d: -f1 | grep -i '^[a-z]'

# Show the project name found in pyproject.toml
show-project-name:
	@echo $(PROJECT_NAME)

# Check for ~/.pypirc
check-pypirc:
	@if [ ! -f $(PYPIRC) ]; then \
		echo "Error: $(PYPIRC) not found. Please create it with your PyPI credentials."; \
		exit 1; \
	fi

# Create and configure virtual environment
$(VENV_NAME):
	$(PYTHON) -m venv $(VENV_NAME)
	./$(VENV_NAME)/bin/pip install --upgrade pip
	./$(VENV_NAME)/bin/pip install build twine

# Check source code for minor issues
srcchecks:
	black src/
	isort src/
	flake8 src/
	ruff check src/
	python -m compileall src/

# Build distribution
build: $(VENV_NAME)
	./$(VENV_NAME)/bin/python -m build --wheel

# Clean build artifacts and virtual environment
clean:
	rm -rf build/ dist/
	rm -rf uv.lock
	rm -rf *.egg-info/
	rm -rf $(VENV_NAME)/
	rm -rf test-install-venv/ local-install-venv/ prod-install-venv
	rm -rf venv/ .venv/
	rm -f *.whl.metadata .??*~
	rm -rf .coverage .pytest_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -r "{}" +
	find . -type f -name "*.pyc" -delete
	command pip cache purge

# Local installation from built distribution
local-install: clean check-pypirc $(VENV_NAME) build
	$(PYTHON) -m venv local-install-venv
	./local-install-venv/bin/python -m pip install --upgrade pip
	./local-install-venv/bin/pip install $$(ls dist/$(PROJECT_NAME_UNDERSCORE)-*.whl)
	@echo ""
	@echo "Now run:    source ./local-install-venv/bin/activate"

# Test PyPI targets
test-publish: clean check-pypirc $(VENV_NAME) build
	./$(VENV_NAME)/bin/twine upload --verbose --repository testpypi dist/*

test-install: clean
	$(PYTHON) -m venv test-install-venv
	./test-install-venv/bin/pip install --force-reinstall --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ $(PROJECT_NAME)
	@echo ""
	@echo "Now run:    source ./test-install-venv/bin/activate"

# Production PyPI targets
prod-publish: clean check-pypirc $(VENV_NAME) build
	@echo "Are you sure you want to publish to production PyPI? [y/N] " && read ans && [ $${ans:-N} = y ]
	./$(VENV_NAME)/bin/twine upload --verbose dist/*

prod-install: clean
	$(PYTHON) -m venv prod-install-venv
	./prod-install-venv/bin/pip install --force-reinstall $(PROJECT_NAME)
	@echo ""
	@echo "Now run:    source ./prod-install-venv/bin/activate"

# Declare targets that don't create a file of the same name
.PHONY: show-make-targets show-project-name check-pypirc srcchecks build clean local-install test-publish test-install prod-publish prod-install

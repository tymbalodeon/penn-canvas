ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYPROJECT := $(ROOT_DIR)/pyproject.toml
COMMAND := $(shell awk -F '[ ="]+' '$$1 == "name" { print $$2 }' $(PYPROJECT))
VERSION := $(shell awk -F '[ ="]+' '$$1 == "version" { print $$2 }' $(PYPROJECT))
ENTRY_POINT := $(ROOT_DIR)/main.py
WHEEL := $(ROOT_DIR)/dist/penn_canvas-$(VERSION)-py3-none-any.whl
REQUIREMENTS = requirements.txt
POETRY = poetry run
PRE_COMMIT = pre-commit run

all: help

binary: ## Build a binary executable with pyinstaller
	poetry run pyinstaller $(ENTRY_POINT) --name "penn-canvas"

black: ## Format code
	$(POETRY) black $(ROOT_DIR)

.PHONY: build
build: ## Build the CLI and isntall it in your global pip packages
	poetry build && pip install $(WHEEL) --force-reinstall

flake: ## Lint code
	$(POETRY) pflake8 $(ROOT_DIR)

format: isort black flake mypy ## Format and lint code

freeze: ## Freeze the dependencies to the requirements.txt file
	poetry export -f $(REQUIREMENTS) --output $(REQUIREMENTS)

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| sort \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

isort: ## Sort imports
	$(POETRY) isort $(ROOT_DIR)

mypy: ## Type-check code
	$(POETRY) $(PRE_COMMIT) mypy -a

sandbox: ## Open an interactive Python shell with connections to Canvas
	tmux new-session -d; \
	tmux send-keys '$(POETRY) bpython' C-m; \
	tmux send-keys 'from sandbox import *' C-m; \
	tmux send-keys 'from penn_canvas.api import list' C-m; \
	tmux attach

shell: ## Run bpython in project virtual environment
	$(POETRY) bpython

try: ## Try a command using the current state of the files without building
ifdef args
	$(POETRY) $(COMMAND) $(args)
else
	$(POETRY) $(COMMAND)
endif

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VERSION := $(shell awk -F '[ ="]+' '$$1 == "version" { print $$2 }' $(ROOT_DIR)/pyproject.toml)
WHEEL := $(ROOT_DIR)/dist/penn_canvas-$(VERSION)-py3-none-any.whl
REQUIREMENTS = requirements.txt
POETRY = poetry run
PRE_COMMIT = pre-commit run
COMMAND = penn-canvas

all: help

black: ## Format code
	$(POETRY) black $(ROOT_DIR)

build: ## Build the CLI and isntall it in your global pip packages
	poetry build && pip install $(WHEEL) --force-reinstall

flake8: ## Lint code
	$(POETRY) flake8 $(ROOT_DIR)

format: isort black flake8 mypy ## Format and lint code

freeze: ## Freeze the dependencies to the requirements.txt file
	poetry export -f $(REQUIREMENTS) --output $(REQUIREMENTS)

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

isort: ## Sort imports
	$(POETRY) isort $(ROOT_DIR)

mypy: ## Type-check code
	$(POETRY) $(PRE_COMMIT) mypy -a

try: ## Try a command using the current state of the files without building
ifdef args
	$(POETRY) $(COMMAND) $(args)
else
	$(POETRY) $(COMMAND)
endif

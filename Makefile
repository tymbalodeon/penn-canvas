ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
WHEEL := $(ROOT_DIR)/buid/penn_canvas-0.1.0-py3-none-any.whl
REQUIREMENTS = requirements.txt
COMMAND := poetry run

all: help

black: ## Format code
	$(COMMAND) black --experimental-string-processing $(ROOT_DIR)

build: ## Build the CLI and isntall it in your global pip packages
	poetry build && pip

flake8: ## Lint code
	$(COMMAND) flake8 $(ROOT_DIR)

format: isort black flake8 ## Format and lint code

freeze: ## Freeze the dependencies to the requirements.txt file
	poetry export -f $(REQUIREMENTS) --output $(REQUIREMENTS)

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

isort: ## Sort imports
	$(COMMAND) isort $(ROOT_DIR)

.DEFAULT_GOAL := help

SRC_DIRS := graphen_trace tests

.PHONY: help install cli frontend-install frontend-dev frontend-build lint test build clean

define PRINT_HELP
Usage:

  make <target>

Available targets:
endef
export PRINT_HELP

help: ## Show available commands
	@printf "\n%s\n\n" "$${PRINT_HELP}"
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@printf "\n"

install: ## Install Python dependencies with Poetry
	@echo "\n> Installing Python dependencies\n"
	poetry install

cli: ## Run the CLI (pass arguments with ARGS="about", for example)
	@echo "\n> Running Graphen Trace CLI\n"
	poetry run graphen-trace $(ARGS)

frontend-install: ## Install frontend dependencies with npm
	@echo "\n> Installing frontend dependencies\n"
	cd frontend && npm ci

frontend-dev: ## Start Vite development server
	@echo "\n> Starting Vite development server\n"
	cd frontend && npm run dev

frontend-build: ## Build frontend into the Python package
	@echo "\n> Building frontend assets\n"
	cd frontend && npm run build

lint: ## Check Python formatting, lint, and frontend types
	@echo "\n> Running code quality checks\n"
	poetry run black --check $(SRC_DIRS)
	poetry run pylint graphen_trace
	cd frontend && npm run lint

test: ## Run Python and frontend tests
	@echo "\n> Running test suites\n"
	poetry run python -m unittest discover
	cd frontend && npm test

build: frontend-build ## Build frontend and Python distributions
	@echo "\n> Building Python distributions\n"
	poetry build

clean: ## Remove generated build files and caches
	@echo "\n> Removing generated files\n"
	rm -rf dist build graphen_trace/web/dist frontend/node_modules frontend/tsconfig.tsbuildinfo

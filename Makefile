.PHONY: help install dev test test-unit test-integration lint format check clean

PYTHON := python
PYTEST := pytest
PIP := pip

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(PIP) install -r requirements.txt

dev:  ## Run the backend in development mode
	PYTHONPATH=. $(PYTHON) -m backend.main

test:  ## Run all tests
	PYTHONPATH=. $(PYTEST) tests/

test-unit:  ## Run unit tests only
	PYTHONPATH=. $(PYTEST) tests/unit/

test-integration:  ## Run integration tests only
	PYTHONPATH=. $(PYTEST) tests/integration/

test-contract:  ## Run contract tests only
	PYTHONPATH=. $(PYTEST) tests/contract/

lint:  ## Run ruff linter
	ruff check backend/ tests/

format:  ## Format code with ruff
	ruff format backend/ tests/

check: lint test  ## Lint and test

clean:  ## Remove build artefacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -f data/aegis.db data/aegis.db-shm data/aegis.db-wal

docker-build:  ## Build the backend Docker image
	docker build -f infrastructure/docker/Dockerfile.backend -t aegis-backend:dev .

docker-up:  ## Start all services via docker-compose
	docker-compose up --build

docker-down:  ## Stop all services
	docker-compose down

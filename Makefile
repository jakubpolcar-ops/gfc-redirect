.PHONY: help lint format check deploy run logs freeze clean

PROJECT_ID    ?= $(shell gcloud config get-value project 2>/dev/null)
REGION        ?= europe-west1
FUNCTION_NAME ?= gfc-redirect
ENTRY_POINT   ?= handle_redirect
RUNTIME       ?= python312

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run linter (ruff check)
	uv run ruff check .

format: ## Format code (ruff format + isort)
	uv run ruff format .
	uv run ruff check --fix --select I .

check: lint ## Run linter + type checker
	uv run mypy main.py config.py database.py

run: ## Run locally on port 8080
	uv run functions-framework --target $(ENTRY_POINT) --debug --port 8080

freeze: ## Generate requirements.txt for GCF deployment
	uv export --no-hashes --no-dev --no-emit-project -o requirements.txt

deploy: freeze lint ## Deploy to Google Cloud Functions (Gen2)
	gcloud functions deploy $(FUNCTION_NAME) \
		--gen2 \
		--runtime $(RUNTIME) \
		--region $(REGION) \
		--trigger-http \
		--allow-unauthenticated \
		--entry-point $(ENTRY_POINT) \
		--source . \
		--memory 256Mi \
		--max-instances 2 \
		--set-env-vars DRIVE_FOLDER_ID=$$DRIVE_FOLDER_ID

logs: ## Tail Cloud Function logs (last 50 entries)
	gcloud functions logs read $(FUNCTION_NAME) \
		--gen2 \
		--region $(REGION) \
		--limit 50

clean: ## Remove cache files and generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name '*.pyc' -delete 2>/dev/null; true
	rm -rf .mypy_cache .ruff_cache

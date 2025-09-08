# -------- Persona Lab Makefile --------
# One-liners for dev vs pi runs, tests, and builds

APP_PORT ?= 8001

# Build metadata (captured at make time)
GIT_SHA    := $(shell git rev-parse --short=12 HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export GIT_SHA GIT_BRANCH BUILD_DATE APP_PORT

.PHONY: help dev-up dev-up-wait dev-down pi-up pi-up-wait pi-down logs test lint curl-health curl-meta wait

help:
	@echo "Targets:"
	@echo "  dev-up        - compose up (dev), rebuild with build metadata"
	@echo "  dev-up-wait   - dev-up and wait until /health is ready"
	@echo "  dev-down      - compose down (dev)"
	@echo "  pi-up         - compose up (pi), rebuild with build metadata"
	@echo "  pi-up-wait    - pi-up and wait until /health is ready"
	@echo "  pi-down       - compose down (pi)"
	@echo "  logs          - follow compose logs"
	@echo "  test          - run pytest in a one-off python:3.11-slim container"
	@echo "  lint          - run ruff in a one-off container"
	@echo "  curl-health   - curl /health"
	@echo "  curl-meta     - curl /__meta"

dev-up:
	docker compose --profile dev up -d --build api-dev

dev-up-wait: dev-up wait

dev-down:
	docker compose --profile dev down

pi-up:
	docker compose --profile pi up -d --build api-pi

pi-up-wait: pi-up wait

pi-down:
	docker compose --profile pi down

logs:
	docker compose logs -f

wait:
	@echo "Waiting for API on port $(APP_PORT) ..."
	@for i in $$(seq 1 30); do \
	  if curl -fsS http://localhost:$(APP_PORT)/health >/dev/null 2>&1; then \
	    echo "API is healthy ✅"; exit 0; \
	  else \
	    sleep 1; \
	  fi; \
	done; \
	echo "API did not become healthy in time ❌"; exit 1

test:
	docker run --rm -v "$$PWD":/work -w /work python:3.11-slim \
	  bash -lc "export PYTHONPATH=/work && pip install -r requirements.txt -r requirements-dev.txt && pytest -q"

lint:
	docker run --rm -v "$$PWD":/work -w /work python:3.11-slim \
	  bash -lc "pip install ruff==0.6.8 && ruff check ."

curl-health:
	curl -s http://localhost:$(APP_PORT)/health

curl-meta:
	curl -s http://localhost:$(APP_PORT)/__meta | jq .

# -------- Persona Lab — Make Targets --------
# Quick ref:
#   make up                # start api + worker, wait for /health
#   make up-all            # start api + worker + monitor profile, wait for /health
#   make down              # stop & remove (and orphans)
#   make ps                # container status
#   make logs              # tail api logs (Ctrl+C to stop)
#   make logs svc=worker   # tail worker logs
#   make logs_once         # show last 100 lines (no follow)
#   make logs_once svc=monitor
#   make smoke             # check API only
#   make smoke-all         # check API + Worker + Monitor (monitor optional)
#   make rebuild           # rebuild images then up
#   make open              # open API & Monitor in browser (on the Pi)

SHELL := /bin/bash
COMPOSE ?= docker compose

# Ports (keep in sync with docker-compose.yml)
API_PORT ?= 8001
WORKER_PORT ?= 8022
MON_PORT ?= 8090

# Default service for log targets
svc ?= api

.PHONY: up up-all down ps logs logs_once rebuild health-wait smoke smoke-all open

up:
	$(COMPOSE) up -d
	@$(MAKE) --no-print-directory health-wait

# Bring up with the monitoring profile (monitor on $(MON_PORT))
up-all:
	$(COMPOSE) --profile monitoring up -d
	@$(MAKE) --no-print-directory health-wait

down:
	$(COMPOSE) down --remove-orphans || true

ps:
	$(COMPOSE) ps

# Tail logs for a specific service (default: api). Ctrl+C to stop.
logs:
	$(COMPOSE) logs -f --no-color $(svc)

# Show the last 100 lines for a service and exit (no follow)
logs_once:
	$(COMPOSE) logs --no-color --tail=100 $(svc)

# Rebuild images and relaunch
rebuild:
	$(COMPOSE) build --no-cache
	$(MAKE) --no-print-directory up

# Wait until API /health returns HTTP 200 (30 x 1s = 30s max)
health-wait:
	@echo "Waiting for API on port $(API_PORT) ..."
	@for i in {1..30}; do \
		if curl -fsS "http://localhost:$(API_PORT)/health" >/dev/null 2>&1; then \
			echo "API is healthy ✅"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "API did not become healthy in time ❌" && exit 1

# One-shot readiness check (API only)
smoke:
	@echo "Smoking API /health ..."
	@curl -fsS "http://localhost:$(API_PORT)/health" >/dev/null 2>&1 || (echo "Smoke failed ❌" && exit 1)
	@echo "Smoke passed ✅"

# Extended readiness: API + Worker + Monitor (monitor optional)
smoke-all:
	@echo "Smoking API /health ..."
	@curl -fsS "http://localhost:$(API_PORT)/health" >/dev/null 2>&1 || (echo "API smoke failed ❌" && exit 1)
	@echo "API smoke passed ✅"
	@echo "Smoking Worker /health ..."
	@curl -fsS "http://localhost:$(WORKER_PORT)/health" >/dev/null 2>&1 || (echo "Worker smoke failed ❌" && exit 1)
	@echo "Worker smoke passed ✅"
	@echo "Smoking Monitor (optional) ..."
	@if curl -fsS "http://localhost:$(MON_PORT)" >/dev/null 2>&1; then \
		echo "Monitor smoke passed ✅"; \
	else \
		echo "Monitor not reachable on :$(MON_PORT) — skipping (start with 'make up-all' to include it)"; \
	fi

# Convenience: open API + Monitor in browser (on the Pi)
open:
	@xdg-open "http://localhost:$(API_PORT)/playground" >/dev/null 2>&1 || true
	@xdg-open "http://localhost:$(MON_PORT)" >/dev/null 2>&1 || true
	@echo "Opened API playground on :$(API_PORT) and monitor on :$(MON_PORT) (if xdg-open is available)"


# Run tests in disposable container
test:
	$(COMPOSE) --profile test run --rm test

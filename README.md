[![CI](https://github.com/elvin-rivera23/persona-lab/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/elvin-rivera23/persona-lab/actions/workflows/ci.yml)

# persona-lab

## Persona Lab — Foundation & Portability

Tiny FastAPI skeleton with Docker + Compose profiles for dev (PC/Mac/Linux) and pi (Raspberry Pi 5).

## Quick Start

```bash
# Copy env template (edit as needed)
cp .env.example .env

# DEV profile (PC/Mac/Linux)
docker compose --profile dev up -d --build api-dev

# PI profile (Raspberry Pi 5)
docker compose --profile pi up -d --build api-pi

# Verify
curl -s http://localhost:8001/health
curl -s http://localhost:8001/version
```

## Stop / Restart

```bash
docker compose --profile dev down
docker compose --profile pi down
docker compose --profile dev build --no-cache api-dev
docker compose --profile dev up -d api-dev
docker compose logs -f
```

## Notes

- Profiles separate dev vs Pi runs but use the same codebase.
- Health and version endpoints exist for checks and monitoring.
- Use `.env` for runtime overrides; commit only `.env.example`.
- Images are portable (amd64/arm64).
- Default API port is 8001 (used in CI).
- If running multiple projects locally, you can override the host port:
  `API_PORT=8002 docker compose up -d api`

## Development

For a consistent workflow, use the Makefile:

```bash
make up          # start api + worker (wait until /health passes)
make up-all      # start api + worker + monitor
make logs        # tail logs (Ctrl+C to stop)
make logs_once   # show last 100 log lines
make smoke-all   # run health checks on all services
make test        # run unit tests in container
make down        # stop and clean up
```

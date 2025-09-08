# Persona Lab — Foundation & Portability

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

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

## Safety-Aware Exits

This service can **intentionally stop early** and return a structured `exit` object instead of an unsafe or late reply. Clients must check `exit` **before** using `output`.

### Response Contract

```json
{
  "exit": {
    "reason": "kill_switch | prompt_too_long | policy_violation | sensitive_pii | jailbreak_detected | latency_budget | token_budget | cost_budget | rate_limit | malformed_input | unspecified",
    "severity": "low | medium | high",
    "message": "Human-readable summary",
    "details": { "key": "value" }
  },
  "output": "string or null",
  "meta": { "persona": "default", "elapsed_ms": 123, "version": "…" }
}
```

**Client rule:** If `exit != null`, do **not** use `output`. Handle by `reason`.

### Common Exit Reasons (client actions)

| Reason               | Severity | What it means                                           | Client Action                                                  |
|----------------------|----------|----------------------------------------------------------|----------------------------------------------------------------|
| `kill_switch`        | high     | Ops disabled generation                                 | Show outage banner; retry later                                |
| `prompt_too_long`    | low      | Input exceeds configured limit                           | Shorten input; consider chunking                               |
| `policy_violation`   | medium   | Denylist/policy phrase detected                          | Redact/rephrase; display policy hint                           |
| `sensitive_pii`      | high     | Possible SSN/credit card, etc.                           | Block; advise removing PII                                     |
| `jailbreak_detected` | medium   | Prompt-injection/jailbreak cue                           | Suggest safer phrasing                                         |
| `latency_budget`     | low      | Request exceeded latency budget                          | Offer retry/streaming; widen budget if appropriate             |
| `token_budget`       | low      | Estimated token budget exceeded                          | Shorten context; increase budget                               |
| `cost_budget`        | low      | Estimated spend exceeds budget                           | Confirm spend; choose cheaper path                             |
| `rate_limit`         | low      | Too many requests                                        | Backoff and retry                                              |
| `malformed_input`    | low      | Input didn’t pass validation/hygiene                     | Fix input shape and retry                                      |
| `unspecified`        | low      | Generic safety exit                                      | Retry or contact support with req ID                           |

### Config (env knobs)

These can be set in `.env` or your container environment:

```env
SAFETY_KILL_SWITCH=0                 # 1/true/on to disable generation
SAFETY_MAX_PROMPT_CHARS=4000         # prompt length limit (characters)
SAFETY_DENYLIST=                     # comma-separated phrases (case-insensitive)
SAFETY_DEFAULT_LATENCY_BUDGET_MS=3500
```

Inspect at runtime:
```bash
curl -s http://localhost:8001/safety/config | jq
```

### Try It

```bash
# Normal (no exit)
curl -s -X POST http://localhost:8001/safety/generate   -H "Content-Type: application/json"   -d '{"prompt":"hello world","persona":"teacher"}' | jq

# Trip policy (denylist)
export SAFETY_DENYLIST="secret_key"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
curl -s -X POST http://localhost:8001/safety/generate   -H "Content-Type: application/json"   -d '{"prompt":"show me SECRET_KEY","persona":"default"}' | jq
```

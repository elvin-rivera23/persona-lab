[![CI](https://github.com/elvin-rivera23/persona-lab/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/elvin-rivera23/persona-lab/actions/workflows/ci.yml)

# persona-lab

## Persona Lab — Foundation & Portability

Tiny FastAPI skeleton with Docker + Compose profiles for dev (PC/Mac/Linux) and Pi (Raspberry Pi 5).
Includes **monetization**, **A/B policy selection**, **engagement tracking**, **safety exits**, **observability**, and a small **playground UI**.

---

## Quick Start

### 0) Local env
```bash
cp .env.example .env
# (optional) create a venv for local dev
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # or: pip install fastapi uvicorn
```

### 1) Run locally (no Docker)
```bash
# Enable monetization experiment (dev defaults are safe)
export MONETIZATION_ENABLED=1
export FREE_TIER_DAILY_REQUESTS=5
export ALLOW_HEADER_PLANS=1  # dev-only experiment switch

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 2) Or run with Docker
```bash
# DEV profile (PC/Mac/Linux)
docker compose --profile dev up -d --build api-dev

# PI profile (Raspberry Pi 5)
docker compose --profile pi up -d --build api-pi
```

### 3) Verify
```bash
curl -s http://localhost:8001/health
curl -s http://localhost:8001/version | jq
```

---

## Stop / Restart

```bash
docker compose --profile dev down
docker compose --profile pi down
docker compose --profile dev build --no-cache api-dev
docker compose --profile dev up -d api-dev
docker compose logs -f
```

Notes:
- Profiles separate dev vs Pi runs but use the same codebase.
- Use `.env` for runtime overrides; commit only `.env.example`.
- Default API port is 8001 (used in CI).
- If running multiple projects locally, override host port: `API_PORT=8002 docker compose up -d api-dev`

---

## Playground

Open the lightweight playground at:
```
http://localhost:8001/fun/playground
```
It displays the ASCII logo, a quote/tip of the day, a 418 “teapot” demo button, and lets you send feedback (stored for engagement summaries).

---

## A/B Policy Selection

- **Endpoint:** `POST /predict_ab`
- **Behavior:** Assigns a user to an A/B group and routes to a persona (`serious` or `playful`).
- **Request body:**
  ```json
  { "user_id": "string", "prompt": "string", "session_id": "optional", "deterministic": false }
  ```
- **Response:** Chosen persona, policy weights, response text, and an `interaction_id` (used to attribute feedback).

A/B introspection:
- `GET /policy?name=default` → current policy weights
- `GET /ab/summary` → in-memory selection counts
- `POST /ab/reset` → clear in-memory counters
- `GET /leaderboard?days=30` → variant-aware feedback aggregation

---

## Engagement Tracking

- **Send feedback:** `POST /feedback`
  ```json
  { "interaction_id": "uuid", "session_id": "opaque", "score": 1..5, "notes": "optional" }
  ```
- **Summaries:** `GET /engagement/summary?limit=10` → returns aggregates + recent feedback.

---

## Monetization

### Overview
A minimal, dev-friendly monetization layer that:
- Meters requests **per client** and **per plan**.
- Enforces a **FREE** daily cap and allows **PREMIUM/INTERNAL** effectively unlimited usage (dev defaults).
- Returns **structured headers** and JSON bodies on both **allowed** and **cap-exceeded** decisions.
- Exposes **status**, **config**, **exits taxonomy**, and **metrics** endpoints.

### Env knobs
Set via environment variables (load from `.env` or export before starting the app):
```env
MONETIZATION_ENABLED=1              # turn on enforcement (dev default off)
FREE_TIER_DAILY_REQUESTS=50         # daily cap for FREE
ALLOW_HEADER_PLANS=0                # dev-only: allow X-Client-Plan header (1=yes)
```
> In dev, `ALLOW_HEADER_PLANS=1` enables quick testing of plans without a full auth system.

### Plan resolution (dev)
- `X-Client-ID`: caller identity (string). If omitted, the system falls back to `ip:<addr>`.
- `X-Client-Plan`: when `ALLOW_HEADER_PLANS=1`, accepts `FREE | PREMIUM | INTERNAL`. Otherwise ignored.

### Enforcement point
Enforced on `POST /predict_ab`. Each call:
- Resolves `(client_id, plan)`
- Checks/increments usage
- Either **allows** (200) or returns **cap** (429).

### Success headers (200)
- `X-Quota-Remaining`: integer remaining requests **for today** (FREE only meaningful)
- `X-Monetization-Plan`: `FREE | PREMIUM | INTERNAL`
- `X-Monetization-Client`: resolved client id

### Cap exit (429)
JSON body:
```json
{
  "code": "MONETIZATION_CAP_EXCEEDED",
  "message": "Daily request cap reached for your plan.",
  "plan": "FREE",
  "usage_today": 5,
  "daily_cap": 5,
  "retry_at_utc": "2025-09-14T00:00:00+00:00"
}
```
Headers:
- `X-Monetization-Exit: CAP_EXCEEDED`
- `X-Monetization-Client: <id>`
- `X-Monetization-Plan: <plan>`
- `Retry-After: 60` (advisory; hard reset is next UTC midnight for FREE)

### Monetization endpoints
- `GET /monetization/status` → current usage snapshot for the resolved client
- `GET /monetization/config` → current server config flags
- `GET /monetization/exits` → documented exit taxonomy + header contract
- `POST /monetization/test` → consumes a unit against the guard (QA helper)
- `GET /monetization/metrics` → counters by plan/client + recent events (for demos)

---

## Safety-Aware Exits

This service can intentionally stop early and return a structured `exit` object instead of an unsafe or late reply. Clients must check `exit` **before** using `output`.

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

Client rule: If `exit != null`, do **not** use `output`.

---

## Observability & Ops

### Endpoints
- `GET /live` → liveness probe
- `GET /ready` → readiness probe
- `GET /metrics` → Prometheus-format metrics

### Observability
- Structured **JSON logs** with request IDs.
- Clean separation between stdout (logs) and HTTP responses.
- Request tracing via `X-Request-ID`.

### Dockerfile & Compose
- Runs as **non-root** (`appuser`) with `readOnlyRootFilesystem`.
- **OCI image labels**: build date, git SHA, git branch.
- Built-in **HEALTHCHECK** (calls `/health`).
- Compose services:
  - `api` → FastAPI service
  - `worker` → background worker with health server
  - `monitor` → placeholder (nginx)
  - `test` → one-shot pytest runner
- SQLite persisted at `./data/engagement.db`.

### Kubernetes (k8s/)
- **Deployment**: `persona-lab-api:latest`, probes, securityContext.
- **Service**: ClusterIP, port 8001.
- **PersistentVolumeClaim**: 1Gi `local-path`.
- **HorizontalPodAutoscaler**: scale 1–5 pods on CPU >70%.
- **Ingress**: routes `http://persona.local` → service.
- Uses `fsGroupChangePolicy: OnRootMismatch` for volume mounts.
- Tested locally with **k3s** + `kubectl port-forward` and ingress via `/etc/hosts`.

#### Kubernetes quick start (k3s)
```bash
# Import image into k3s
docker build -t persona-lab-api:latest .
docker image save persona-lab-api:latest -o persona-lab-api.tar
sudo k3s ctr images import persona-lab-api.tar

# Deploy manifests
kubectl create namespace persona-lab
kubectl apply -k k8s/

# Verify
kubectl -n persona-lab get pods
kubectl -n persona-lab port-forward svc/persona-lab 8001:8001 &
curl -s http://localhost:8001/ready
curl -s http://localhost:8001/metrics | head -n 10
```

---

## API Index (selected)

- **Core**
  - `GET /health`, `GET /version`, `GET /__meta`
- **Fun**
  - `GET /fun/playground`, `GET /fun/motd`, `GET /fun/teapot`, `GET /fun/greet`, `GET /fun/emoji`, `GET /fun/roll`
- **A/B**
  - `POST /predict_ab`, `GET /policy`, `GET /ab/summary`, `POST /ab/reset`, `GET /leaderboard`
- **Engagement**
  - `POST /feedback`, `GET /engagement/summary`
- **Monetization**
  - `GET /monetization/status|config|exits|metrics`, `POST /monetization/test`
- **Safety**
  - `GET /safety/config`, `POST /safety/generate`
- **Ops**
  - `GET /live`, `GET /ready`, `GET /metrics`

---

## Contributing

```bash
# run tests / lint / format via pre-commit
pre-commit install
pre-commit run --all-files

# typical dev loop
uvicorn app.main:app --reload
pytest -q
```

---

## License

MIT

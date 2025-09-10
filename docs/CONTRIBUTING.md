# Contributing

## Branch / PR flow
- Create a feature branch from `main`: `feat/<topic>`
- Open a PR; CI must pass (lint, unit-tests, docker build).
- One approval required to merge (self-approval OK for solo dev).

## Local dev quickstart
```bash
python -m pip install -U pip
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
pytest -q
```

## Commit style
- Use `feat:`, `fix:`, `chore:`, `ci:`, `docs:` etc.
- Keep commits small; explain *why*, not just *what*.

## Security
- Never commit secrets. Use `.env` and keep it out of git.
- See SECURITY.md for reporting.

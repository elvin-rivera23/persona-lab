FROM python:3.11-slim

ARG APP_USER=appuser
ARG APP_HOME=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -d ${APP_HOME} ${APP_USER}
WORKDIR ${APP_HOME}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY VERSION ./VERSION

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8001 \
    WORKERS=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${APP_PORT}/health || exit 1

USER ${APP_USER}

CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT} --workers ${WORKERS}"]

FROM python:3.11-slim

ARG APP_USER=appuser
ARG APP_HOME=/app

# Build metadata (passed from compose/Makefile)
ARG BUILD_DATE="unknown"
ARG GIT_SHA="unknown"
ARG GIT_BRANCH="unknown"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -d ${APP_HOME} ${APP_USER}
WORKDIR ${APP_HOME}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + version file
COPY app ./app
COPY VERSION ./VERSION

# Runtime env (can be overridden)
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8001 \
    WORKERS=1 \
    PYTHONUNBUFFERED=1 \
    BUILD_DATE=${BUILD_DATE} \
    GIT_SHA=${GIT_SHA} \
    GIT_BRANCH=${GIT_BRANCH}

# OCI labels (nice-to-have metadata)
LABEL org.opencontainers.image.created=${BUILD_DATE} \
      org.opencontainers.image.revision=${GIT_SHA} \
      org.opencontainers.image.version=${GIT_SHA}

EXPOSE 8001

# Use /ready instead of /health so the container only goes healthy when the app is ready
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${APP_PORT}/ready || exit 1

USER ${APP_USER}

CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT} --workers ${WORKERS}"]

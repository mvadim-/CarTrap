# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    APP_MODULE=cartrap.main:app \
    PORT=8000

WORKDIR /app

COPY backend/pyproject.toml backend/setup.py backend/README.md /tmp/backend/
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import pathlib, subprocess, tomllib; project = tomllib.loads(pathlib.Path('/tmp/backend/pyproject.toml').read_text()); packages = list(project['build-system']['requires']) + list(project['project']['dependencies']); subprocess.run(['pip', 'install', *packages], check=True)" \
    && python -m playwright install --with-deps chromium

COPY backend/pyproject.toml backend/setup.py backend/README.md /app/backend/
COPY backend/src /app/backend/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps /app/backend

ENV PYTHONPATH=/app/backend/src

CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT}"]

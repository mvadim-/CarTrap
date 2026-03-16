FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODULE=cartrap.main:app \
    PORT=8000

WORKDIR /app

COPY backend /app/backend
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/backend

ENV PYTHONPATH=/app/backend/src

CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT}"]

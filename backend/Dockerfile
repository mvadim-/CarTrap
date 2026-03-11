FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend /app/backend
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/backend

ENV PYTHONPATH=/app/backend/src

CMD ["uvicorn", "cartrap.main:app", "--host", "0.0.0.0", "--port", "8000"]

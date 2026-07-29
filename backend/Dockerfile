FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SESSION_DATABASE_PATH=/app/runtime/replay.sqlite3

WORKDIR /app

COPY backend /app/backend
COPY knowledge /app/knowledge
COPY evaluation /app/evaluation

RUN python -m pip install --upgrade pip \
    && python -m pip install /app/backend

RUN mkdir -p /app/runtime

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "noname.main:app", "--host", "0.0.0.0", "--port", "8000"]

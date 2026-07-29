FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REPLAY_PROJECT_ROOT=/app \
    SESSION_STORAGE=memory \
    SESSION_DATABASE_PATH=/app/runtime/replay.sqlite3

WORKDIR /app

COPY backend /app/backend
COPY knowledge /app/knowledge
COPY evaluation /app/evaluation

RUN python -m pip install --upgrade pip \
    && python -m pip install /app/backend

WORKDIR /app/backend
RUN python -m noname.evaluation \
    && python -m noname.benchmark

RUN mkdir -p /app/runtime

ENV SESSION_STORAGE=sqlite

EXPOSE 8000

CMD ["uvicorn", "noname.main:app", "--host", "0.0.0.0", "--port", "8000"]

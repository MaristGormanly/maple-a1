FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/server/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY server /app/server

RUN mkdir -p /app/data/raw /app/data/cache /app/uploads/rubrics

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn server.app.main:app --host 0.0.0.0 --port 8000"]

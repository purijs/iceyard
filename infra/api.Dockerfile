FROM python:3.12-slim

WORKDIR /app

COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY apps/api/iceyard_api /app/apps/api/iceyard_api
COPY apps/api/alembic.ini /app/apps/api/alembic.ini
COPY apps/api/alembic /app/apps/api/alembic

RUN pip install --no-cache-dir -e /app/apps/api

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["uvicorn", "iceyard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Linux container for the operational REST/WebSocket surface.
# The MT5 terminal itself is intentionally not containerized here; the
# Python/MT5 market-data runtime must be deployed with a compatible MT5 host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-api.txt requirements-api.txt
RUN python -m pip install --no-cache-dir -r requirements-api.txt

COPY . .
RUN useradd --create-home --uid 10001 botuser && mkdir -p data && chown -R botuser:botuser /app
USER botuser

CMD ["python", "scripts/run_runtime_api.py"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-realtime.txt requirements-realtime.txt
COPY requirements-bot.txt requirements-bot.txt
RUN python -m pip install --no-cache-dir -r requirements-realtime.txt -r requirements-bot.txt

COPY . .
RUN useradd --create-home --uid 10001 botuser && mkdir -p data && chown -R botuser:botuser /app
USER botuser

CMD ["python", "scripts/run_bot.py"]

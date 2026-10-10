FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/chess-coach.db STOCKFISH_PATH=/usr/games/stockfish
RUN apt-get update && apt-get install -y --no-install-recommends stockfish curl && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home coach && mkdir -p /data && chown coach:coach /data
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt
COPY --chown=coach:coach backend/app ./app
USER coach
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=4 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-server-header"]

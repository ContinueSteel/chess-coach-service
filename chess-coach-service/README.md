# Chess Coach

A private, browser-first chess training MVP. Import completed Chess.com games or PGN files, analyse every move with Stockfish, review mover-relative evaluations, and solve puzzles generated from positions before your mistakes. Optional OpenAI-compatible commentary never blocks deterministic engine coaching.

## Start from a clean clone

Requirements: Docker Engine with Compose v2.

```bash
git clone https://github.com/ContinueSteel/chess-coach-service.git
cd chess-coach-service/chess-coach-service
cp .env.example .env
docker compose up --build -d
```

Open **http://localhost:8081**. The same nginx origin serves the UI and `/api`; the backend has no host port.

Health checks:

```bash
curl -fsS http://localhost:8081/api/health
curl -fsS http://localhost:8081/api/ready
```

Stop without deleting data: `docker compose down`. Delete all data only when intended: `docker compose down -v`.

## Browser workflow

1. **Settings:** choose depth (6–24) or a per-move time limit, configure loss/puzzle thresholds, and optionally configure a local or OpenAI-compatible model.
2. **Import:** paste one or multiple PGNs, upload a `.pgn` file (2 MB maximum), or fetch 1–12 recent public Chess.com archive months.
3. **Games:** open a persisted game and start analysis. The worker is bounded to one game at a time; poll status remains responsive.
4. **Review:** navigate positions and see the played move, mover-relative centipawn loss, engine choice, PV, classification, and deterministic coach note.
5. **Puzzles:** generated positions start before a qualifying mistake. Enter legal UCI (`e2e4`) or SAN (`Nf3`), request progressive hints, and persist attempts.

Classifications are explicit and testable: loss `0` = best, `<20` = great, below the configured inaccuracy threshold = good, then inaccuracy/mistake/blunder at configured thresholds. Mate scores use ±100,000. The app deliberately does not claim moves are “brilliant.”

## Configuration

`CHESS_COACH_PORT` in `.env` selects the public frontend port (default `8081`). User settings live in SQLite and are editable in the UI:

- Chess.com username and archive month bound
- Stockfish depth or time per move
- inaccuracy, mistake, blunder, and puzzle centipawn thresholds
- AI provider: disabled, local, or OpenAI-compatible base URL/model/API key

The API key is masked in API responses and never logged. It is stored unencrypted in the local SQLite volume. Engine analysis and coaching work with AI disabled. A failed AI request falls back to engine commentary.

## Development and tests

Backend (the container command avoids host Python-version differences):

```bash
docker run --rm -v "$PWD/backend:/work" -w /work python:3.12-slim sh -c \
  "pip install -r requirements-dev.txt && PYTHONPATH=. pytest -q"
```

Frontend:

```bash
cd frontend-react
npm ci
npm run typecheck
npm run build
npm audit --audit-level=high
```

Full deterministic release smoke:

```bash
./scripts/smoke.sh
```

It performs a clean Compose build, checks UI/API health, round-trips settings, ingests and analyses a tactical fixture with real Stockfish, exercises puzzle hints/attempts, recreates containers, and verifies SQLite persistence.

## Backup and upgrade

The named volume is `chess-coach_chess_data` under the default Compose project name.

```bash
# Consistent backup (brief stop)
docker compose down
docker run --rm -v chess-coach_chess_data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/chess-coach-backup.tgz -C /data .
docker compose up -d

# Restore into an empty volume
docker compose down -v
docker volume create chess-coach_chess_data
docker run --rm -v chess-coach_chess_data:/data -v "$PWD:/backup" alpine \
  tar xzf /backup/chess-coach-backup.tgz -C /data
docker compose up -d
```

For an upgrade, take a backup, pull the target revision, then run `docker compose up --build -d`. Schema creation is additive for this MVP.

## Security and publication

This is a **single-user application with no authentication**. The backend is internal to Compose and only nginx publishes a port, but the UI exposes all local chess data and settings to anyone who can reach it. Before exposing it to the untrusted internet, put it behind TLS and authentication (for example, an authenticated reverse proxy or VPN), restrict network access, use a secrets manager for AI keys, and establish backups. Do not commit `.env`, database files, or real credentials.

Chess.com imports use the documented public archives endpoint with an identifying User-Agent. Replace the placeholder contact in `backend/app/chesscom.py` with a real operational contact before a broad public deployment.

## API

FastAPI documentation is available internally through `http://localhost:8081/api/docs`. Important endpoints include `/api/settings`, `/api/games`, `/api/games/import-pgn`, `/api/games/upload`, `/api/games/import-chesscom`, `/api/games/{id}/analysis`, and `/api/puzzles`.

## Known MVP limits

- One in-process analysis worker; queued work does not survive an abrupt process kill, though game data does.
- No accounts, auth, TLS, cloud object storage, or multi-user isolation.
- Puzzle verification checks the engine's first move rather than a full forced line.
- AI configuration is optional; up to ten significant mistakes per analysis receive AI-enhanced notes when configured, with deterministic fallback on any provider failure.

# Chess Coach 0.2.0

A private, browser-first chess training application. It imports PGNs and recent public Chess.com games, analyses every move with local Stockfish, supports interactive review/trials/puzzles, and keeps settings and history in SQLite. Optional OpenAI-compatible text coaching never blocks engine analysis.

## Run

Requirements: Docker Engine and Compose v2.

```bash
cp .env.example .env
docker compose up --build -d
```

Open **http://localhost:8081**. Health: `curl -fsS http://localhost:8081/api/ready`.
Stop without deleting data with `docker compose down`; only `docker compose down -v` deletes the database volume.

## Browser controls

- **Import:** paste/upload PGN or fetch 1–12 completed public Chess.com archive months.
- **Review:** a completed game opens after White's first move. Left/right arrows navigate plies unless a form, dialog, or board drag has focus. The notation list groups White and Black under each full-move number.
- **Orientation:** Chess.com imports infer the named player's color. Unknown PGNs expose a White/Black bottom override.
- **Engine cues:** selecting a played move shows its pre-move position; yellow = best move. Expected replies and continuations are listed with their exact later-PV FEN context rather than drawn illegally on the current board. Reanalyse v0.1 records to add cues.
- **Trial moves:** move a piece from any reviewed position for non-mutating Stockfish evaluation and level-appropriate feedback.
- **Puzzles:** solve by moving pieces. Hints state the side to move and use named files (for example, `f-file`).
- **Annotations:** right-drag draws arrows and right-click highlights a square. On touch/mobile, enable **Annotate**, then tap start/end squares; tap one square twice to highlight it.
- **Trainer:** move a piece and type its coordinate notation.
- **Sounds:** local Web Audio move click; enable/disable and set volume in Settings.
- **Chat:** asks bounded position/game questions using server-derived canonical PGN, FEN, and Stockfish data. The UI gives a structured unavailable state while AI is disabled.

All ordinary configuration is browser-editable and persisted: coaching level, board colors, piece style preference, coordinates, orientation, sound, engine limits/thresholds, Chess.com username, and optional text provider.

### Coaching levels

- **Beginner:** plain language and one core concept.
- **Intermediate:** plans plus an accessible concrete line.
- **Advanced:** titled-player-oriented candidate moves, calculation, and stable endpoints. It does not claim the model or application has title-level authority.

## AI configuration

AI is optional. Deterministic Stockfish coaching, analysis, trials, and puzzles work with it disabled. For chat/enhanced notes, select a local or OpenAI-compatible provider and set an HTTP(S) base URL plus model. The default local endpoint is `http://host.docker.internal:11434/v1`; Compose maps that hostname to the Docker host gateway so it resolves on Linux as well as Docker Desktop. Keys are masked in API responses and never sent to the browser after saving, but are stored unencrypted in the local SQLite volume. Null, empty, malformed, timed-out, or failed provider responses fall back per note and cannot fail game analysis.

## Upgrade and backup

v0.2 uses versioned, idempotent SQLite migration (`PRAGMA user_version=2`). Startup upgrades a v0.1 database by adding `games.player_color`, `coach_messages`, and new setting rows without deleting games, analysis, puzzles, or attempts.

```bash
# Backup consistently
 docker compose down
 docker run --rm -v chess-coach_chess_data:/data -v "$PWD:/backup" alpine \
   tar czf /backup/chess-coach-backup.tgz -C /data .
 docker compose up -d

# Upgrade after backup
 git checkout <0.2 revision>
 docker compose up --build -d
```

## Development and release gates

```bash
# Backend
cd backend
python3.12 -m venv .venv-v02
.venv-v02/bin/pip install -r requirements-dev.txt pip-audit
.venv-v02/bin/python -m pytest -q
.venv-v02/bin/pip-audit -r requirements.txt

# Frontend
cd ../frontend-react
npm ci
npm test
npm run typecheck
npm run build
npm audit --audit-level=high

# E2E with bundled Chromium container (candidate on port 18082)
cd ..
CHESS_COACH_PORT=18082 docker compose -p chess-coach-v02 up --build -d
docker run --rm -v "$PWD:/work" -w /work --network host \
  mcr.microsoft.com/playwright:v1.57.0-noble bash -lc \
  'npm --prefix frontend-react ci >/dev/null && frontend-react/node_modules/.bin/playwright test --config=playwright.config.ts'
```

The E2E suite checks review keyboard navigation, settings, deletion, annotations, puzzle board mode, browser errors, and square board geometry at 320, 375, 600, 768, 900, 1024, and 1440 px.

## Licensing and attribution

- Application source: repository license.
- `react-chessboard` 5.12.1: MIT, Ryan Gregory/Clariity.
- Classic, Alpha, and Merida-inspired piece renderers in `frontend-react/src/pieces.tsx`: original simplified SVG geometry created for this application, locally bundled under the repository license. The style names describe the visual families; no third-party Alpha or Merida artwork is copied.
- `chess.js` 1.4.0: BSD-2-Clause.
- Stockfish: GPLv3, installed as a separate OS package and process in the backend image. See the distribution's Stockfish package/source offer obligations when redistributing images.
- Move sounds are generated locally with the Web Audio API; no external audio asset or CDN is used.

## Security scope

This is a **single-user application with no authentication or TLS**. Nginx is the only published Compose service, but anyone who can reach it can access chess data and settings. Before untrusted-network exposure, add authenticated TLS at a reverse proxy/VPN, restrict network access, protect backups, and move provider secrets to a secrets manager.

## API highlights

FastAPI docs: `/api/docs`. Main routes: `/api/settings`, `/api/games`, `/api/games/{id}/analysis`, `DELETE /api/games/{id}`, `/api/puzzles`, `/api/positions/evaluate-trial`, and `/api/games/{id}/chat`.

## Deliberate limits

- One in-process analysis worker and bounded synchronous interactive engine work; queued jobs do not survive abrupt process death (interrupted state is made restartable).
- Puzzle checking validates Stockfish's first move, not a complete forced line.
- No accounts, multi-user isolation, auth, or TLS.

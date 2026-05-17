# AGENTS.md

## Cursor Cloud specific instructions

### Overview
Context Hub is a local-only Python application that scans developer tool activity (Cursor agent transcripts, etc.), indexes it into SQLite, and exposes it via a **CLI** (Typer) and **web dashboard** (FastAPI + Jinja2).

### Running the application

- **CLI**: `python3 -m context_hub.cli <command>` — see `README.md` Quickstart for command list.
- **Web UI**: `python3 -m uvicorn context_hub.api:app --host 0.0.0.0 --port 8000` — dashboard at `http://localhost:8000/`.
- **Database init**: `python3 -m context_hub.cli init-db` — idempotent, safe to re-run.

### Key caveats

- **click compatibility**: The project requires `click<8.2` to work with `typer>=0.12,<0.13`. If click 8.2+ is installed, CLI option parsing breaks (options like `--project-path` refuse values). The update script pins `click<8.2` explicitly.
- **No tests directory**: The repository currently has no automated tests. Verification is manual via CLI commands and the web UI.
- **No linter/formatter config**: No flake8, ruff, mypy, or similar configuration is present.
- **Cursor provider default path** is hardcoded for Windows (`C:\Users\Home Network\...`). On Linux, configure via `python3 -m context_hub.cli config set cursor_path <path>` before scanning.
- **SQLite DB location**: `~/.context_hub/context.db`. Config at `~/.context_hub/config.json`.

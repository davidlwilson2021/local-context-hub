# AGENTS.md

## Cursor Cloud specific instructions

### Overview
Context Hub is a local-only Python application that scans developer tool activity (Cursor agent transcripts, etc.), indexes it into SQLite, and exposes it via a **CLI** (Typer) and **web dashboard** (FastAPI + Jinja2).

### Running the application

- **CLI**: `python3 -m context_hub.cli <command>` — see `README.md` Quickstart for command list.
- **Web UI**: `python3 -m context_hub.cli serve` — dashboard at `http://127.0.0.1:8000/` (use `--allow-lan` only with `api_token` set).
- **Database init**: `python3 -m context_hub.cli init-db` — idempotent, safe to re-run.

### Key caveats

- **click compatibility**: The project requires `click<8.2` to work with `typer>=0.12,<0.13`. If click 8.2+ is installed, CLI option parsing breaks (options like `--project-path` refuse values). The update script pins `click<8.2` explicitly.
- **Tests**: `pytest tests/` — uses isolated temp config/db via fixtures.
- **No linter/formatter config**: No flake8, ruff, mypy, or similar configuration is present.
- **Cursor paths**: Auto-detected on Linux/macOS/Windows via `paths.py`; override with `python3 -m context_hub.cli config set cursor_path <path>`.
- **Security**: When `api_token` is set, all routes (HTML and JSON) require `?token=`, `Authorization: Bearer`, or `X-Context-Hub-Token`.
- **SQLite DB location**: `~/.context_hub/context.db` (mode 0600 on Unix). Config at `~/.context_hub/config.json`.

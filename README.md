## Context Hub

Local-only **Context Hub** for aggregating activity from developer tools (starting with Cursor and Cowork) by project and time.

### Features (MVP)

- **Scan local app data** (e.g., Cursor agent transcripts) and index activity into a SQLite database.
- **Group activity by project** path and app (Cursor, Cowork, etc.).
- **CLI commands** to initialize the database, scan sources, and list recent activity or projects.
- Optional **local web UI** to browse projects and activity in your browser.

### Tech stack

- **Language**: Python 3 (Anaconda-friendly).
- **Storage**: SQLite (local file under your home directory).
- **CLI**: Typer.
- **Web API/UI (optional)**: FastAPI + Jinja2 + Uvicorn.

### Quickstart

1. Create and activate a Python environment (e.g., via Anaconda).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize the database:

```bash
python -m context_hub.cli init-db
```

4. Configure paths (example for Cursor on this machine):

```bash
python -m context_hub.cli config set cursor_path "C:\\Users\\Home Network\\AppData\\Local\\Programs\\system context"
```

5. Scan and view recent activity:

```bash
python -m context_hub.cli scan --apps cursor
python -m context_hub.cli recent --limit 20
```

### Privacy

- All data is stored **locally** on your machine.
- You can configure which apps and paths to include or ignore.

---

## Personal knowledge base (Second Brain scaffold)

This repo also includes **`my-knowledge-base/`**, a flat-file layout for a Karpathy-style second brain: three folders plus a schema file, no database.

### Layout

```
my-knowledge-base/
  CLAUDE.md    # schema / rules for your AI (edit YOUR TOPIC and interests)
  raw/         # source material — paste articles, notes, exports here
  wiki/        # organized wiki — maintained by your AI from raw/ + schema
  outputs/     # answers, reports, research outputs
```

1. Put sources in `raw/`.
2. Edit `CLAUDE.md` with your topic and wiki rules.
3. Point your AI at `my-knowledge-base/` and ask it to compile or update `wiki/` from `raw/` following `CLAUDE.md`, starting with `wiki/INDEX.md`.

Optional: use [agent-browser](https://github.com/vercel-labs/agent-browser) (or similar) to scrape URLs into `raw/`. Run periodic wiki health checks as described in `CLAUDE.md`. Repository-wide agent guidance for coding work lives in **`AGENTS.md`**; knowledge-base-specific rules stay in **`my-knowledge-base/CLAUDE.md`**.

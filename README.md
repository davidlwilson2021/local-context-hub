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


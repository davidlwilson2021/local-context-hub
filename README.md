## Context Hub

Local-only **Context Hub** for aggregating activity from developer tools (Cursor, Cowork, and more) by project and time.

### Features

- **Scan** local app data (Cursor agent transcripts, Cowork JSON/JSONL) into SQLite with **deduplication** and **incremental** skips.
- **CLI** and **web dashboard** with search, filters, project detail pages, and transcript viewer.
- **Export** per-project context packs (Markdown / JSON) for agents and standups.
- **Security**: localhost-by-default server, optional API token, gated filesystem paths.

### Tech stack

- Python 3, SQLite, Typer, FastAPI, Jinja2, Uvicorn.

### Quickstart

```bash
pip install -r requirements.txt 'click<8.2'
python -m context_hub.cli init-db
python -m context_hub.cli doctor          # auto-detect Cursor paths
python -m context_hub.cli scan --apps cursor,cowork
python -m context_hub.cli serve           # http://127.0.0.1:8000/
```

On Linux/macOS, Cursor paths are auto-detected under `~/.cursor` when possible. Override with:

```bash
python -m context_hub.cli config set cursor_path /path/to/cursor/data
```

### Web dashboard

```bash
python -m context_hub.cli serve
```

- Filter by search text, app, and activity kind.
- Click a project for its timeline; open transcripts when indexed.
- **Scan now** triggers a rescan from the dashboard.

Expose on your LAN only with an API token (required):

```bash
python -m context_hub.cli config token-generate
python -m context_hub.cli serve --allow-lan
# Open http://<host>:8000/?token=<your-token>
```

Do not run raw `uvicorn` with `--host 0.0.0.0`; use `cli serve` instead.

### Security

| Topic | Behavior |
|--------|----------|
| **Threat model** | Single trusted user on one machine. A **LAN attacker** can read indexed dev context if you bind `0.0.0.0` without `api_token`. |
| **Bind address** | `serve` binds to `127.0.0.1` unless `--allow-lan` (`0.0.0.0`). `--allow-lan` **requires** `api_token`. |
| **Auth** | When `api_token` is set, **all** routes (HTML + JSON) require `?token=`, `Authorization: Bearer <token>`, or `X-Context-Hub-Token`. |
| **Raw paths** | Omitted from API unless authenticated or `expose_raw_paths` is enabled. |
| **Metadata** | Only `source` by default; full metadata (paths, content) requires auth or `expose_metadata`. |
| **Transcript reads** | Only files under configured `cursor_path` / `cowork_path` roots; scan skips paths outside roots. |
| **Exports** | Path redaction via `redact_paths_on_export` (default on). |
| **Local files** | `~/.context_hub/` created with mode `0700`; DB/config `0600` on Unix. |

### Configuration keys

- `cursor_path`, `cowork_path` — data roots (auto-detected if unset for Cursor).
- `ignore_paths`, `ignore_apps` — comma-separated exclusions (`ignore_paths` uses resolved path prefix matching).
- `store_full_content` — store transcript excerpts in metadata (larger DB).
- `use_transcript_titles` — use conversation titles as summaries (default off; titles may contain secrets).
- `api_token` — protect all web routes.
- `expose_raw_paths`, `expose_metadata` — include sensitive fields without auth (not recommended).
- `redact_paths_on_export` — redact home directory paths in exports.

### API (JSON)

- `GET /projects?q=&app=`
- `GET /activity?limit=&app=&project_path=&q=&kind=&since=&until=`
- `POST /scan` body `{"apps":"cursor,cowork"}`
- `GET /export/markdown?project_path=`
- `GET /export/json?project_path=`
- `GET /transcript?raw_path=` (must be under configured roots)

### CLI reference

| Command | Description |
|---------|-------------|
| `init-db` | Create SQLite schema |
| `doctor` | Path and config health check |
| `scan` | Index activities (deduped) |
| `serve` | Web UI (localhost default) |
| `recent`, `projects`, `show` | Browse from terminal |
| `export --project-path PATH` | Markdown or JSON context pack |
| `config set/show`, `config token-generate` | Settings |

### Privacy

All data stays **local** (`~/.context_hub/context.db` and `config.json`). Scanning imports Cursor/Cowork data that may include secrets in paths or titles — use `ignore_paths`, keep `use_transcript_titles` off, and set `api_token` on shared machines.

### Tests

```bash
pytest tests/
```

from __future__ import annotations

import secrets
from typing import Optional

import typer

from .db import get_config_path, get_db_path, init_db, load_config, save_config
from .paths import default_cursor_paths, find_agent_transcripts_dir, iter_existing_paths
from .service import activity_for_project, projects_with_last_activity, recent_activity, scan_and_store


app = typer.Typer(help="Context Hub CLI")
config_app = typer.Typer(help="View and edit Context Hub configuration.")
app.add_typer(config_app, name="config")


@app.command("init-db")
def init_db_cmd() -> None:
    """Initialize the SQLite database (idempotent)."""
    init_db()
    typer.echo(f"Initialized database at {get_db_path()}")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    cfg = load_config()
    typer.echo(cfg.model_dump_json(indent=2))
    typer.echo(f"\nConfig file: {get_config_path()}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ...,
        help=(
            "Key: cursor_path, cowork_path, ignore_paths, ignore_apps, "
            "store_full_content, api_token, expose_raw_paths, redact_paths_on_export"
        ),
    ),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value."""
    cfg = load_config()

    if key == "cursor_path":
        cfg.cursor_path = value
    elif key == "cowork_path":
        cfg.cowork_path = value
    elif key == "ignore_paths":
        cfg.ignore_paths = [v.strip() for v in value.split(",") if v.strip()]
    elif key == "ignore_apps":
        cfg.ignore_apps = [v.strip().lower() for v in value.split(",") if v.strip()]
    elif key == "store_full_content":
        cfg.store_full_content = value.lower() in ("1", "true", "yes", "on")
    elif key == "expose_raw_paths":
        cfg.expose_raw_paths = value.lower() in ("1", "true", "yes", "on")
    elif key == "redact_paths_on_export":
        cfg.redact_paths_on_export = value.lower() in ("1", "true", "yes", "on")
    elif key == "api_token":
        cfg.api_token = value.strip() or None
    else:
        raise typer.BadParameter(f"Unknown config key: {key}")

    save_config(cfg)
    typer.echo(f"Updated {key} in config.")


@config_app.command("token-generate")
def config_token_generate() -> None:
    """Generate and save a random API token for the web server."""
    cfg = load_config()
    cfg.api_token = secrets.token_urlsafe(32)
    save_config(cfg)
    typer.echo("Generated api_token (save this — it is stored in config):")
    typer.echo(cfg.api_token)


@app.command("doctor")
def doctor() -> None:
    """Check configuration, paths, and database health."""
    cfg = load_config()
    typer.echo("Context Hub doctor")
    typer.echo(f"- Database: {get_db_path()} ({'ok' if get_db_path().exists() else 'missing — run init-db'})")
    typer.echo(f"- Config: {get_config_path()}")

    transcripts = find_agent_transcripts_dir(cfg.cursor_path)
    if transcripts:
        typer.echo(f"- Cursor transcripts: {transcripts} (ok)")
    else:
        typer.echo("- Cursor transcripts: not found")
        typer.echo("  Candidates:")
        for p in iter_existing_paths(default_cursor_paths()):
            sub = p / "agent-transcripts"
            marker = " (has agent-transcripts)" if sub.is_dir() else ""
            typer.echo(f"    {p}{marker}")

    if cfg.cowork_path:
        cp = cfg.cowork_path
        typer.echo(f"- Cowork path: {cp} ({'ok' if __import__('pathlib').Path(cp).is_dir() else 'missing'})")
    else:
        typer.echo("- Cowork path: not configured")

    if cfg.api_token:
        typer.echo("- API token: set (API routes require Authorization: Bearer <token>)")
    else:
        typer.echo("- API token: not set (API open on localhost — set api_token for shared machines)")

    if cfg.expose_raw_paths:
        typer.echo("- expose_raw_paths: enabled (filesystem paths visible in API)")


@app.command("scan")
def scan(
    apps: str = typer.Option(
        "cursor",
        "--apps",
        help="Comma-separated list of apps to scan (e.g., cursor,cowork)",
    ),
) -> None:
    """Scan configured apps and store activity in the database."""
    app_list = [a.strip().lower() for a in apps.split(",") if a.strip()]
    results = scan_and_store(app_list)

    if not results:
        typer.echo("No providers were run. Check your config or app names.")
        raise typer.Exit(code=1)

    typer.echo("Scan complete:")
    for name, stats in results.items():
        typer.echo(
            f"- {name}: {stats['inserted']} inserted, {stats['skipped']} skipped (dupes/unchanged)"
        )


@app.command("serve")
def serve(
    port: int = typer.Option(8000, "--port", "-p"),
    allow_lan: bool = typer.Option(
        False,
        "--allow-lan",
        help="Bind 0.0.0.0 (exposes the dashboard on your network). Default is localhost only.",
    ),
) -> None:
    """Run the web dashboard (localhost by default)."""
    import uvicorn

    host = "0.0.0.0" if allow_lan else "127.0.0.1"
    if allow_lan:
        typer.echo("Warning: --allow-lan exposes Context Hub on your network. Set api_token in config.")
    typer.echo(f"Starting server at http://{host}:{port}/")
    uvicorn.run("context_hub.api:app", host=host, port=port, reload=False)


@app.command("recent")
def recent(
    limit: int = typer.Option(20, "--limit", "-n"),
    app_name: Optional[str] = typer.Option(None, "--app"),
    query: Optional[str] = typer.Option(None, "--q", help="Search summary text"),
) -> None:
    """Show recent activity across apps."""
    rows = recent_activity(limit=limit, app_name=app_name, query=query)
    if not rows:
        typer.echo("No activity found.")
        return

    for row in rows:
        ts = row["timestamp"].isoformat(timespec="seconds")
        app_label = row["app"] or "unknown"
        project = row["project_path"] or ""
        summary = row["summary"]
        line = f"{ts} [{app_label}] {summary}"
        if project:
            line += f"  ({project})"
        typer.echo(line)


@app.command("projects")
def projects(
    query: Optional[str] = typer.Option(None, "--q"),
    app_name: Optional[str] = typer.Option(None, "--app"),
) -> None:
    """List discovered projects with their last activity timestamp."""
    rows = projects_with_last_activity(query=query, app_name=app_name)
    if not rows:
        typer.echo("No projects found.")
        return

    for row in rows:
        last_ts = row["last_activity"].isoformat(timespec="seconds") if row["last_activity"] else "never"
        app_label = row["app"] or "unknown"
        typer.echo(f"{last_ts} [{app_label}] {row['name']} - {row['path']}")


@app.command("show")
def show(
    project_path: str = typer.Option(..., "--project-path"),
) -> None:
    """Show all activity for a given project (newest first)."""
    rows = activity_for_project(project_path)
    if not rows:
        typer.echo(f"No activity found for project: {project_path}")
        return

    for row in rows:
        ts = row["timestamp"].isoformat(timespec="seconds")
        app_label = row["app"] or "unknown"
        summary = row["summary"]
        typer.echo(f"{ts} [{app_label}] {summary}")


@app.command("export")
def export_cmd(
    project_path: str = typer.Option(..., "--project-path"),
    format: str = typer.Option("markdown", "--format", "-f", help="markdown or json"),
) -> None:
    """Export a project context pack to stdout."""
    from .service import export_project_json, export_project_markdown
    import json

    if format == "json":
        payload = export_project_json(project_path)
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(export_project_markdown(project_path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

from __future__ import annotations

from typing import Optional

import typer

from .db import load_config, save_config, init_db, get_db_path, get_config_path
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
    key: str = typer.Argument(..., help="Configuration key (cursor_path, cowork_path, ignore_paths, ignore_apps, store_full_content)"),
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
    else:
        raise typer.BadParameter(f"Unknown config key: {key}")

    save_config(cfg)
    typer.echo(f"Updated {key} in config.")


@app.command("scan")
def scan(
    apps: str = typer.Option(
        "cursor",
        "--apps",
        help="Comma-separated list of apps to scan (e.g., cursor,cowork)",
    )
) -> None:
    """Scan configured apps and store activity in the database."""
    app_list = [a.strip().lower() for a in apps.split(",") if a.strip()]
    results = scan_and_store(app_list)

    if not results:
        typer.echo("No providers were run. Check your config or app names.")
        raise typer.Exit(code=1)

    typer.echo("Scan complete:")
    for name, count in results.items():
        typer.echo(f"- {name}: {count} activities inserted")


@app.command("recent")
def recent(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of activity items to show"),
    app_name: Optional[str] = typer.Option(None, "--app", help="Filter by app name (e.g., cursor)"),
) -> None:
    """Show recent activity across apps."""
    rows = recent_activity(limit=limit, app_name=app_name)
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
def projects() -> None:
    """List discovered projects with their last activity timestamp."""
    rows = projects_with_last_activity()
    if not rows:
        typer.echo("No projects found.")
        return

    for row in rows:
        last_ts = row["last_activity"].isoformat(timespec="seconds") if row["last_activity"] else "never"
        app_label = row["app"] or "unknown"
        typer.echo(f"{last_ts} [{app_label}] {row['name']} - {row['path']}")


@app.command("show")
def show(
    project_path: str = typer.Option(..., "--project-path", help="Filesystem path of the project to inspect"),
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()


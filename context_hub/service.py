from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from .db import (
    get_activities_for_project,
    get_activity_by_raw_path,
    get_scan_mtime,
    get_session,
    init_db,
    insert_activities,
    list_projects_with_last_activity,
    list_recent_activity,
    load_config,
    upsert_scan_state,
)
from .models import ActivityItem, Config
from .paths import path_is_under, resolve_cursor_base_path
from .providers.cursor_provider import CursorProvider
from .providers.cowork_provider import CoworkProvider
from .redact import redact_activity_row, redact_path


def _build_providers(config: Config, app_names: Iterable[str]):
    """Instantiate providers for the requested apps."""
    normalized = {name.lower() for name in app_names}
    providers = []

    if "cursor" in normalized and "cursor" not in (config.ignore_apps or []):
        base = resolve_cursor_base_path(config.cursor_path)
        providers.append(CursorProvider(base_path=base, store_full_content=config.store_full_content))

    if "cowork" in normalized and "cowork" not in (config.ignore_apps or []):
        providers.append(CoworkProvider(base_path=config.cowork_path))

    return providers


def _filter_ignored(items: Iterable[ActivityItem], config: Config) -> List[ActivityItem]:
    ignore_paths = config.ignore_paths or []
    if not ignore_paths:
        return list(items)

    def is_ignored(item: ActivityItem) -> bool:
        path = item.project_path or str(item.metadata.get("project_path", ""))
        return any(path.startswith(prefix) for prefix in ignore_paths)

    return [item for item in items if not is_ignored(item)]


def _activity_to_dict(activity, *, include_raw_path: bool) -> dict[str, Any]:
    row = {
        "id": activity.id,
        "timestamp": activity.timestamp,
        "app": activity.app.name if activity.app else None,
        "project_path": activity.project.path if activity.project else None,
        "kind": activity.kind,
        "summary": activity.summary,
        "metadata": activity.extra or {},
    }
    if include_raw_path:
        row["raw_path"] = activity.raw_path
    return row


def _serialize_rows(rows: List[dict], *, redact_paths: bool) -> List[dict]:
    if not redact_paths:
        return rows
    return [redact_activity_row(r, redact_paths=True) for r in rows]


def scan_and_store(app_names: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Run providers and store results. Returns per-app inserted/skipped counts."""
    init_db()
    config = load_config()
    if app_names is None:
        app_names = ["cursor"]

    providers = _build_providers(config, app_names)
    from .db import activity_exists, get_or_create_app, insert_activities

    results: Dict[str, Any] = {}
    with get_session() as session:
        for provider in providers:
            raw_items = list(provider.scan())
            items = _filter_ignored(raw_items, config)
            app = get_or_create_app(session, name=provider.name)
            incremental: List[ActivityItem] = []
            unchanged = 0
            for item in items:
                if not item.raw_path:
                    incremental.append(item)
                    continue
                try:
                    mtime = float(item.metadata.get("mtime") or Path(item.raw_path).stat().st_mtime)
                except OSError:
                    incremental.append(item)
                    continue
                prev = get_scan_mtime(session, provider.name, item.raw_path)
                if prev is not None and prev >= mtime and activity_exists(session, app.id, item.raw_path):
                    unchanged += 1
                    continue
                incremental.append(item)

            inserted, skipped = insert_activities(session, incremental)
            skipped += unchanged
            for item in items:
                if item.raw_path:
                    try:
                        mtime = Path(item.raw_path).stat().st_mtime
                        upsert_scan_state(session, provider.name, item.raw_path, mtime)
                    except OSError:
                        pass
            results[provider.name] = {"inserted": inserted, "skipped": skipped}

    return results


def recent_activity(
    limit: int = 20,
    app_name: Optional[str] = None,
    *,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    include_raw_path: bool = False,
    redact_paths: bool = False,
):
    init_db()
    with get_session() as session:
        activities = list_recent_activity(
            session,
            limit=limit,
            app_name=app_name,
            query=query,
            kind=kind,
            since=since,
            until=until,
        )
        rows = [_activity_to_dict(a, include_raw_path=include_raw_path) for a in activities]
        return _serialize_rows(rows, redact_paths=redact_paths)


def projects_with_last_activity(
    *,
    query: Optional[str] = None,
    app_name: Optional[str] = None,
):
    init_db()
    with get_session() as session:
        rows = list_projects_with_last_activity(session)
        result = []
        for project, last_ts in rows:
            if app_name and (not project.app or project.app.name != app_name):
                continue
            if query:
                q = query.lower()
                if q not in project.name.lower() and q not in project.path.lower():
                    continue
            result.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "path": project.path,
                    "app": project.app.name if project.app else None,
                    "last_activity": last_ts,
                }
            )
        return result


def activity_for_project(
    project_path: str,
    *,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
    include_raw_path: bool = False,
    redact_paths: bool = False,
):
    init_db()
    with get_session() as session:
        activities = get_activities_for_project(
            session,
            project_path=project_path,
            query=query,
            kind=kind,
            limit=limit,
        )
        rows = [_activity_to_dict(a, include_raw_path=include_raw_path) for a in activities]
        return _serialize_rows(rows, redact_paths=redact_paths)


def get_project_detail(project_path: str, **kwargs):
    projects = projects_with_last_activity()
    project = next((p for p in projects if p["path"] == project_path), None)
    activities = activity_for_project(project_path, **kwargs)
    return project, activities


def read_transcript(raw_path: str) -> Optional[dict[str, Any]]:
    """Read transcript file if it lies under configured provider roots."""
    config = load_config()
    path = Path(raw_path)
    if not path.is_file():
        return None

    allowed_roots: List[Path] = []
    cursor_base = resolve_cursor_base_path(config.cursor_path)
    if cursor_base:
        allowed_roots.append(cursor_base.resolve())
    if config.cowork_path:
        allowed_roots.append(Path(config.cowork_path).resolve())

    if not any(path_is_under(path, root) for root in allowed_roots):
        return None

    lines: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
    except OSError:
        return None

    return {"path": str(path), "lines": lines}


def export_project_markdown(
    project_path: str,
    *,
    redact_paths: Optional[bool] = None,
    include_raw_path: bool = False,
) -> str:
    config = load_config()
    if redact_paths is None:
        redact_paths = config.redact_paths_on_export

    project, activities = get_project_detail(
        project_path,
        include_raw_path=include_raw_path,
        redact_paths=redact_paths,
    )
    title = project["name"] if project else project_path
    lines = [f"# Context pack: {title}", ""]
    if project and project.get("last_activity"):
        lines.append(f"_Last activity: {project['last_activity'].isoformat(timespec='seconds')}_")
        lines.append("")

    for row in activities:
        ts = row["timestamp"].isoformat(timespec="seconds")
        lines.append(f"## {ts} — {row.get('kind', 'other')}")
        lines.append("")
        lines.append(row["summary"])
        meta = row.get("metadata") or {}
        content = meta.get("content_preview") or meta.get("full_content")
        if content:
            lines.append("")
            lines.append("```")
            lines.append(str(content)[:8000])
            lines.append("```")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_project_json(
    project_path: str,
    *,
    redact_paths: Optional[bool] = None,
    include_raw_path: bool = False,
) -> dict[str, Any]:
    config = load_config()
    if redact_paths is None:
        redact_paths = config.redact_paths_on_export

    project, activities = get_project_detail(
        project_path,
        include_raw_path=include_raw_path,
        redact_paths=redact_paths,
    )
    return {
        "project": project,
        "activities": [
            {
                **row,
                "timestamp": row["timestamp"].isoformat(timespec="seconds"),
            }
            for row in activities
        ],
    }


def project_url(project_path: str) -> str:
    return f"/projects/view?path={quote(project_path, safe='')}"

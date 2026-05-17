from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .db import (
    get_activities_for_project,
    get_session,
    init_db,
    list_projects_with_last_activity,
    list_recent_activity,
    load_config,
)
from .models import ActivityItem, Config
from .providers.cursor_provider import CursorProvider
from .providers.cowork_provider import CoworkProvider


def _build_providers(config: Config, app_names: Iterable[str]):
    """Instantiate providers for the requested apps."""
    normalized = {name.lower() for name in app_names}
    providers = []

    if "cursor" in normalized and "cursor" not in (config.ignore_apps or []):
        providers.append(CursorProvider(base_path=config.cursor_path))

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


def scan_and_store(app_names: Optional[Iterable[str]] = None) -> Dict[str, int]:
    """Run providers for the given apps and store results in the database.

    Returns a mapping of app name to number of activities inserted.
    """
    init_db()
    config = load_config()
    if app_names is None:
        app_names = ["cursor"]

    providers = _build_providers(config, app_names)

    from .db import insert_activities  # local import to avoid circulars

    results: Dict[str, int] = {}
    with get_session() as session:
        for provider in providers:
            raw_items = list(provider.scan())
            items = _filter_ignored(raw_items, config)
            count = insert_activities(session, items)
            results[provider.name] = count

    return results


def recent_activity(limit: int = 20, app_name: Optional[str] = None):
    """Return recent activity as simple dictionaries for CLI/API consumption."""
    init_db()
    with get_session() as session:
        activities = list_recent_activity(session, limit=limit, app_name=app_name)
        result = []
        for a in activities:
            result.append(
                {
                    "timestamp": a.timestamp,
                    "app": a.app.name if a.app else None,
                    "project_path": a.project.path if a.project else None,
                    "kind": a.kind,
                    "summary": a.summary,
                    "raw_path": a.raw_path,
                }
            )
        return result


def projects_with_last_activity():
    """Return projects and their last activity timestamp as dictionaries."""
    init_db()
    with get_session() as session:
        rows = list_projects_with_last_activity(session)
        result = []
        for project, last_ts in rows:
            result.append(
                {
                    "name": project.name,
                    "path": project.path,
                    "app": project.app.name if project.app else None,
                    "last_activity": last_ts,
                }
            )
        return result


def activity_for_project(project_path: str):
    """Return all activities for a given project path, newest first."""
    init_db()
    with get_session() as session:
        activities = get_activities_for_project(session, project_path=project_path)
        result = []
        for a in activities:
            result.append(
                {
                    "timestamp": a.timestamp,
                    "app": a.app.name if a.app else None,
                    "project_path": a.project.path if a.project else None,
                    "kind": a.kind,
                    "summary": a.summary,
                    "raw_path": a.raw_path,
                }
            )
        return result


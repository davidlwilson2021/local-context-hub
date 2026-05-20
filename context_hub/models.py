from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class App(BaseModel):
    """Logical application that can emit activity (e.g., cursor, cowork)."""

    id: Optional[int] = Field(default=None)
    name: str
    display_name: str


class Project(BaseModel):
    """A project or workspace, usually identified by a filesystem path."""

    id: Optional[int] = Field(default=None)
    name: str
    path: str
    app_id: Optional[int] = Field(default=None)


class ActivityKind:
    EDIT = "edit"
    CHAT = "chat"
    RUN = "run"
    NOTE = "note"
    OTHER = "other"


class ActivityItem(BaseModel):
    """Single activity event from a tool."""

    id: Optional[int] = Field(default=None)
    app_name: str
    project_path: Optional[str] = Field(default=None)
    timestamp: datetime
    kind: str = Field(default=ActivityKind.OTHER)
    summary: str
    raw_path: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Config(BaseModel):
    """User configuration stored alongside the SQLite database."""

    cursor_path: Optional[str] = None
    cowork_path: Optional[str] = None
    ignore_paths: list[str] = Field(default_factory=list)
    ignore_apps: list[str] = Field(default_factory=list)
    store_full_content: bool = False
    api_token: Optional[str] = None
    expose_raw_paths: bool = False
    redact_paths_on_export: bool = True


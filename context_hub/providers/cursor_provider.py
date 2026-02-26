from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from ..models import ActivityItem, ActivityKind
from .base import BaseProvider


# Default Cursor/system-context AppData path for this machine.
DEFAULT_CURSOR_APPDATA = Path(
    r"C:\Users\Home Network\AppData\Local\Programs\system context"
)


class CursorProvider(BaseProvider):
    """Provider that reads Cursor agent transcripts and emits ActivityItem objects."""

    def __init__(self, base_path: Optional[str | Path] = None) -> None:
        super().__init__(name="cursor")
        self.base_path = Path(base_path) if base_path else DEFAULT_CURSOR_APPDATA

    def _agent_transcripts_dir(self) -> Path:
        return self.base_path / "agent-transcripts"

    def scan(self) -> Iterable[ActivityItem]:
        transcripts_dir = self._agent_transcripts_dir()
        if not transcripts_dir.exists() or not transcripts_dir.is_dir():
            return []

        items: list[ActivityItem] = []
        for path in sorted(transcripts_dir.glob("*.jsonl")):
            item = self._parse_transcript_file(path)
            if item is not None:
                items.append(item)
        return items

    def _parse_transcript_file(self, path: Path) -> Optional[ActivityItem]:
        project_path: Optional[str] = None
        metadata: dict = {
            "source": "cursor_agent_transcript",
            "file": str(path),
        }

        try:
            stat = path.stat()
            # Normalize to naive UTC for consistency.
            timestamp = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(tzinfo=None)
            summary = path.stem.replace("_", " ")

            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Timestamp heuristics.
                    for key in ("created_at", "createdAt", "timestamp", "ts"):
                        if key in record:
                            raw_value = str(record[key])
                            try:
                                parsed = datetime.fromisoformat(raw_value)
                                # If parsed is timezone-aware, convert to UTC and strip tzinfo
                                # so all stored timestamps are naive UTC.
                                if parsed.tzinfo is not None:
                                    parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                                timestamp = parsed
                            except Exception:
                                # Keep fallback mtime if parsing fails.
                                pass
                            break

                    # Title / summary heuristics.
                    title = record.get("title") or record.get("conversation_title")
                    if isinstance(title, str) and title.strip():
                        summary = title.strip()

                    # Workspace / project path heuristics.
                    candidate_keys = [
                        "workspaceRoot",
                        "workspace_path",
                        "workspacePath",
                        "project_path",
                        "projectPath",
                        "cwd",
                    ]
                    for key in candidate_keys:
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            project_path = value.strip()
                            metadata["project_path"] = project_path
                            break

                    # We only look at the first meaningful JSON line.
                    break
        except OSError:
            # If we can't stat or read the file, skip it.
            return None

        return ActivityItem(
            app_name="cursor",
            project_path=project_path,
            timestamp=timestamp,
            kind=ActivityKind.CHAT,
            summary=summary,
            raw_path=str(path),
            metadata=metadata,
        )


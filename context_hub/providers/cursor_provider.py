from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ..models import ActivityItem, ActivityKind
from ..paths import find_agent_transcripts_dir, resolve_cursor_base_path
from .base import BaseProvider


class CursorProvider(BaseProvider):
    """Provider that reads Cursor agent transcripts and emits ActivityItem objects."""

    def __init__(
        self,
        base_path: Optional[str | Path] = None,
        *,
        store_full_content: bool = False,
    ) -> None:
        super().__init__(name="cursor")
        self._configured_base = str(base_path) if base_path else None
        self.store_full_content = store_full_content
        resolved = resolve_cursor_base_path(self._configured_base)
        self.base_path = resolved

    def _agent_transcripts_dir(self) -> Optional[Path]:
        if self.base_path:
            transcripts = self.base_path / "agent-transcripts"
            if transcripts.is_dir():
                return transcripts
        return find_agent_transcripts_dir(self._configured_base)

    def scan(self) -> Iterable[ActivityItem]:
        transcripts_dir = self._agent_transcripts_dir()
        if not transcripts_dir:
            return []

        items: list[ActivityItem] = []
        for path in sorted(transcripts_dir.glob("*.jsonl")):
            item = self._parse_transcript_file(path)
            if item is not None:
                items.append(item)
        return items

    def _parse_transcript_file(self, path: Path) -> Optional[ActivityItem]:
        stat = path.stat()
        timestamp = datetime.fromtimestamp(stat.st_mtime)
        summary = path.stem.replace("_", " ")
        project_path: Optional[str] = None
        metadata: dict = {
            "source": "cursor_agent_transcript",
            "file": str(path),
            "mtime": stat.st_mtime,
        }
        content_lines: list[str] = []

        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    content_lines.append(line)
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    for key in ("created_at", "createdAt", "timestamp", "ts"):
                        if key in record:
                            try:
                                timestamp = datetime.fromisoformat(str(record[key]).replace("Z", "+00:00"))
                            except Exception:
                                pass
                            break

                    title = record.get("title") or record.get("conversation_title")
                    if isinstance(title, str) and title.strip():
                        summary = title.strip()

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

                    if self.store_full_content:
                        text = record.get("text") or record.get("content") or record.get("message")
                        if isinstance(text, str) and text.strip():
                            metadata.setdefault("content_parts", []).append(text.strip()[:4000])

                    break
        except OSError:
            return None

        if self.store_full_content and content_lines:
            joined = "\n".join(content_lines)
            metadata["full_content"] = joined[:50000]
            metadata["content_preview"] = joined[:2000]

        return ActivityItem(
            app_name="cursor",
            project_path=project_path,
            timestamp=timestamp,
            kind=ActivityKind.CHAT,
            summary=summary,
            raw_path=str(path),
            metadata=metadata,
        )

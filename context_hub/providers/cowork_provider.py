from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ..models import ActivityItem, ActivityKind
from ..paths import path_is_under
from .base import BaseProvider


class CoworkProvider(BaseProvider):
    """Provider for Cowork activity logs (JSON/JSONL files under configured directory)."""

    def __init__(self, base_path: Optional[str | Path] = None) -> None:
        super().__init__(name="cowork")
        self.base_path = Path(base_path).resolve() if base_path else None

    def scan(self) -> Iterable[ActivityItem]:
        if self.base_path is None or not self.base_path.is_dir():
            return []

        root = self.base_path.resolve()
        items: list[ActivityItem] = []
        for pattern in ("*.jsonl", "*.json"):
            for path in sorted(self.base_path.rglob(pattern)):
                if not path_is_under(path, root):
                    continue
                item = self._parse_file(path, root)
                if item is not None:
                    items.append(item)
        return items

    def _parse_file(self, path: Path, root: Path) -> Optional[ActivityItem]:
        if not path_is_under(path, root):
            return None

        try:
            stat = path.stat()
        except OSError:
            return None

        timestamp = datetime.fromtimestamp(stat.st_mtime)
        summary = path.stem.replace("_", " ")
        project_path: Optional[str] = None
        metadata: dict = {
            "source": "cowork",
            "file": str(path),
            "mtime": stat.st_mtime,
        }

        try:
            if path.suffix == ".jsonl":
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        summary, project_path, timestamp = self._apply_record(
                            record, summary, project_path, timestamp, metadata
                        )
                        break
            else:
                record = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(record, dict):
                    summary, project_path, timestamp = self._apply_record(
                        record, summary, project_path, timestamp, metadata
                    )
        except (OSError, json.JSONDecodeError):
            return None

        return ActivityItem(
            app_name="cowork",
            project_path=project_path,
            timestamp=timestamp,
            kind=ActivityKind.OTHER,
            summary=summary,
            raw_path=str(path),
            metadata=metadata,
        )

    def _apply_record(self, record, summary, project_path, timestamp, metadata):
        title = record.get("title") or record.get("summary") or record.get("name")
        if isinstance(title, str) and title.strip():
            summary = title.strip()

        for key in ("project_path", "projectPath", "workspace", "cwd"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                project_path = value.strip()
                metadata["project_path"] = project_path
                break

        for key in ("timestamp", "created_at", "createdAt"):
            if key in record:
                try:
                    timestamp = datetime.fromisoformat(str(record[key]).replace("Z", "+00:00"))
                except Exception:
                    pass
                break

        return summary, project_path, timestamp

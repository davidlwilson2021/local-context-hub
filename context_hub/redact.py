from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_HOME = str(Path.home())
_PATH_PATTERN = re.compile(r"(/[\w./-]+|[A-Za-z]:\\[\w\\.-]+)")


def redact_path(value: str, replacement: str = "[path]") -> str:
    if not value:
        return value
    redacted = value.replace(_HOME, replacement)
    return _PATH_PATTERN.sub(replacement, redacted)


def redact_activity_row(row: dict[str, Any], redact_paths: bool) -> dict[str, Any]:
    if not redact_paths:
        return row
    out = dict(row)
    if out.get("project_path"):
        out["project_path"] = redact_path(str(out["project_path"]))
    if out.get("raw_path"):
        out["raw_path"] = redact_path(str(out["raw_path"]))
    if out.get("summary"):
        out["summary"] = redact_path(str(out["summary"]))
    return out

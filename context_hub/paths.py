from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Iterable, List, Optional


def default_cursor_paths() -> List[Path]:
    """Return likely Cursor / agent-transcript roots for this OS (newest first)."""
    candidates: List[Path] = []
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Programs" / "system context")
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            candidates.append(Path(userprofile) / ".cursor")
    elif system == "Darwin":
        home = Path.home()
        candidates.extend(
            [
                home / "Library" / "Application Support" / "Cursor",
                home / ".cursor",
            ]
        )
    else:
        home = Path.home()
        candidates.extend(
            [
                home / ".cursor",
                home / ".config" / "cursor",
                home / ".local" / "share" / "cursor",
            ]
        )

    # Cloud / Linux agent layout (this environment).
    cloud = Path("/opt/cursor")
    if cloud.exists():
        candidates.append(cloud)

    seen: set[str] = set()
    unique: List[Path] = []
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_agent_transcripts_dir(explicit: Optional[str | Path] = None) -> Optional[Path]:
    """Resolve the directory containing agent-transcripts JSONL files."""
    if explicit:
        base = Path(explicit)
        transcripts = base / "agent-transcripts"
        if transcripts.is_dir():
            return transcripts
        if base.name == "agent-transcripts" and base.is_dir():
            return base
        return None

    for base in default_cursor_paths():
        transcripts = base / "agent-transcripts"
        if transcripts.is_dir():
            return transcripts
    return None


def resolve_cursor_base_path(configured: Optional[str]) -> Optional[Path]:
    """Pick configured path or first auto-detected base with transcripts."""
    if configured:
        base = Path(configured)
        if (base / "agent-transcripts").is_dir():
            return base
        if base.name == "agent-transcripts" and base.parent.exists():
            return base.parent
        return base

    for base in default_cursor_paths():
        if (base / "agent-transcripts").is_dir():
            return base
    return None


def path_is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def iter_existing_paths(paths: Iterable[Path]) -> List[Path]:
    return [p for p in paths if p.exists()]

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from ..models import ActivityItem
from .base import BaseProvider


class CoworkProvider(BaseProvider):
    """Stub provider for Cowork.

    For now this only validates that the configured directory exists and logs what
    it would scan. It does not yet emit ActivityItem objects.
    """

    def __init__(self, base_path: Optional[str | Path] = None) -> None:
        super().__init__(name="cowork")
        self.base_path = Path(base_path) if base_path else None

    def scan(self) -> Iterable[ActivityItem]:
        if self.base_path is None:
            # Not configured; nothing to do.
            return []

        if not self.base_path.exists() or not self.base_path.is_dir():
            # Path is configured but missing; silently skip for now.
            return []

        # Placeholder: you can later walk this directory and emit ActivityItem
        # objects based on Cowork's actual file formats.
        return []


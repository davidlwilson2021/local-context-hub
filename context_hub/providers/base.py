from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from ..models import ActivityItem


class BaseProvider(ABC):
    """Abstract base class for app-specific providers."""

    name: str

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def scan(self) -> Iterable[ActivityItem]:
        """Scan underlying data sources and yield ActivityItem objects."""
        raise NotImplementedError


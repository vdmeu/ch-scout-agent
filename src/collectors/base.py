from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Post:
    """A forum/issue post collected from an external source."""
    source: str          # "stackoverflow" | "hackernews" | "reddit" | "github"
    external_id: str     # platform-specific unique ID
    url: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class BaseCollector(ABC):
    """Abstract base for all source collectors."""

    def __init__(self, lookback_seconds: int = 86400):
        self.lookback_seconds = lookback_seconds

    @abstractmethod
    async def collect(self) -> list[Post]:
        """Fetch recent posts. Returns empty list on any error."""
        ...

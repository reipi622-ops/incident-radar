from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class RawItem:
    """Normalized raw item from any collector."""
    external_id: str
    source_name: str
    source_url: Optional[str]
    raw_text: str
    raw_timestamp: Optional[datetime]
    media_items: List[dict] = field(default_factory=list)
    language: Optional[str] = None
    extra: dict = field(default_factory=dict)


class BaseCollector(ABC):
    """All collectors must implement this interface."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def collect(self) -> List[RawItem]:
        """Fetch and return a list of raw items from the source."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name}>"

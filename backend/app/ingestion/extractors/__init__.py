"""Document extractors package."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedPage:
    """A single page/section extracted from a document."""
    text: str
    page_number: int
    metadata: dict[str, str] = field(default_factory=dict)

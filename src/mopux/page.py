from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a listing.

    The API uses three shapes and ``Page`` accepts all of them: Laravel ``{data, links, meta}``,
    page fields inside the object (``{members, page, last_page, total}``) and plain lists
    (comments and notifications up to API 1.1, without totals).
    """

    items: list[T] = field(default_factory=list)
    current_page: int = 1
    last_page: int | None = None
    per_page: int | None = None
    total: int | None = None

    @classmethod
    def parse(cls, data: Any, item: Callable[[Any], T], page: int = 1, per_page: int | None = None) -> Page[T]:
        """Laravel paginator or a plain list."""
        if isinstance(data, list):
            return cls([item(entry) for entry in data], page, None, per_page, None)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            raw_meta = data.get("meta")
            meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
            return cls(
                [item(entry) for entry in data["data"]],
                _int(meta.get("current_page")) or page,
                _int(meta.get("last_page")),
                _int(meta.get("per_page")) or per_page,
                _int(meta.get("total")),
            )
        return cls([], page, None, per_page, None)

    @classmethod
    def parse_fields(cls, data: Any, items_key: str, item: Callable[[Any], T], per_page: int | None = None) -> Page[T]:
        """Page fields inside the object, with the items under ``items_key``."""
        record: dict[str, Any] = data if isinstance(data, dict) else {}
        raw_entries = record.get(items_key)
        entries: list[Any] = raw_entries if isinstance(raw_entries, list) else []
        return cls(
            [item(entry) for entry in entries],
            _int(record.get("page")) or 1,
            _int(record.get("last_page")),
            per_page,
            _int(record.get("total")),
        )

    def has_more(self) -> bool:
        if not self.items:
            return False
        if self.last_page is not None:
            return self.current_page < self.last_page
        return self.per_page is not None and len(self.items) >= self.per_page

    def next_page(self) -> int | None:
        return self.current_page + 1 if self.has_more() else None

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

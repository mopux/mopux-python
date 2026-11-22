from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from ..page import Page

T = TypeVar("T")


async def iterate_pages(fetch: Callable[[int], Awaitable[Page[T]]], first_page: int = 1) -> AsyncIterator[T]:
    """Walks every page lazily, yielding items one by one; stops if the API repeats a page."""
    page: int | None = first_page
    while page is not None:
        result = await fetch(page)
        for item in result.items:
            yield item
        next_page = result.next_page()
        page = next_page if next_page is not None and next_page > page else None

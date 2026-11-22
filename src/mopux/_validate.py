from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date as Date

from .errors import InvalidInputError

_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_HOURS = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")


def id_(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidInputError(field, f"expected a positive integer id, {value!r} given.")
    return value


def ids(values: Iterable[int], field: str) -> list[int]:
    return [id_(value, field) for value in values]


def text(value: str, field: str, max_length: int | None = None) -> str:
    stripped = value.strip()
    if not stripped:
        raise InvalidInputError(field, "cannot be empty.")
    if max_length is not None and len(stripped) > max_length:
        raise InvalidInputError(field, f"may not be longer than {max_length} characters.")
    return stripped


def title(value: str, field: str = "title") -> str:
    return text(value, field, 255)


def date(value: str | Date, field: str) -> str:
    if isinstance(value, Date):
        return value.isoformat()
    match = _DATE.match(value.strip())
    if match is None:
        raise InvalidInputError(field, f'expected YYYY-MM-DD, "{value}" given.')
    try:
        Date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        raise InvalidInputError(field, f'"{value}" is not a valid date.') from None
    return value.strip()


def hours(value: str | int, field: str) -> str:
    """``HH:MM`` (also ``H:MM`` or ``HH:MM:SS``) or minutes; at most 99:59."""
    if isinstance(value, bool):
        raise InvalidInputError(field, "expected HH:MM or minutes.")
    if isinstance(value, int):
        if value < 0:
            raise InvalidInputError(field, "minutes cannot be negative.")
        h, m = divmod(value, 60)
    else:
        match = _HOURS.match(value.strip())
        if match is None:
            raise InvalidInputError(field, f'expected HH:MM, "{value}" given.')
        h, m = int(match[1]), int(match[2])
    if m > 59 or h > 99:
        raise InvalidInputError(field, "expected at most 99:59.")
    return f"{h:02d}:{m:02d}"


def per_page(value: int, maximum: int = 100) -> int:
    if not 1 <= value <= maximum:
        raise InvalidInputError("per_page", f"must be between 1 and {maximum}.")
    return value


def page(value: int) -> int:
    if value < 1:
        raise InvalidInputError("page", "must be 1 or greater.")
    return value

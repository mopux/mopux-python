from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidInputError


@dataclass(frozen=True)
class Upload:
    """A file to upload (task documents, comment attachments)."""

    content: bytes
    filename: str
    content_type: str

    @classmethod
    def from_path(cls, path: str | Path, filename: str | None = None, content_type: str | None = None) -> Upload:
        file = Path(path)
        name = filename or file.name
        return cls.from_bytes(file.read_bytes(), name, content_type)

    @classmethod
    def from_bytes(cls, content: bytes | str, filename: str, content_type: str | None = None) -> Upload:
        if not filename.strip():
            raise InvalidInputError("filename", "cannot be empty.")
        data = content.encode() if isinstance(content, str) else content
        guessed = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return cls(data, filename, guessed)

    def as_httpx(self) -> tuple[str, bytes, str]:
        return (self.filename, self.content, self.content_type)

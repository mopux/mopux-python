"""Generates src/mopux/_sync from src/mopux/_async. Run with --check in CI to fail on drift."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src/mopux/_async"
TARGET = ROOT / "src/mopux/_sync"

RULES: list[tuple[str, str]] = [
    (r"\basync def\b", "def"),
    (r"\basync for\b", "for"),
    (r"\basync with\b", "with"),
    (r"\bawait\s+", ""),
    (r"\bAsyncIterator\b", "Iterator"),
    (r"\bAwaitable\[(.*?)\]", r"\1"),
    (r", Awaitable\b", ""),
    (r"\bhttpx\.AsyncClient\b", "httpx.Client"),
    (r"\bimport asyncio\b", "import time"),
    (r"\basyncio\.sleep\b", "time.sleep"),
    (r"\baclose\b", "close"),
    (r"__aenter__", "__enter__"),
    (r"__aexit__", "__exit__"),
    (r"\bAsync([A-Z]\w*)", r"\1"),
    (r"async with AsyncMopux", "with Mopux"),
]

HEADER = "# Generated from src/mopux/_async by scripts/unasync.py. Do not edit.\n"


def convert(source: str) -> str:
    for pattern, replacement in RULES:
        source = re.sub(pattern, replacement, source)
    return HEADER + source


def formatted(files: dict[str, str]) -> dict[str, str]:
    """Runs ruff format on the generated sources, so CI compares formatted code."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files.items():
            (Path(tmp) / name).write_text(content)
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--quiet", "--config", str(ROOT / "pyproject.toml"), tmp],
            check=True,
        )
        return {name: (Path(tmp) / name).read_text() for name in files}


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    expected = formatted({path.name: convert(path.read_text()) for path in sorted(SOURCE.glob("*.py"))})
    TARGET.mkdir(exist_ok=True)
    for name, content in expected.items():
        target = TARGET / name
        if target.exists() and target.read_text() == content:
            continue
        stale.append(name)
        if not check:
            target.write_text(content)
    for extra in TARGET.glob("*.py"):
        if extra.name not in expected:
            stale.append(extra.name)
            if not check:
                extra.unlink()
    if check and stale:
        print(f"src/mopux/_sync is out of date ({', '.join(stale)}). Run: python scripts/unasync.py")
        return 1
    print("src/mopux/_sync is up to date." if not stale else f"Regenerated {', '.join(stale)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

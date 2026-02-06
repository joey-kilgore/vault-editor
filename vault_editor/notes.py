from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

MARKER_PATTERN = re.compile(
    r"<!--\s*(?P<kind>IMAGE|BOOK|AIIMAGE|MOVIE)\s*:\s*(?P<query>[^|>]+?)\s*(\|\s*(?P<alt>[^>]+?)\s*)?-->",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ImageMarker:
    kind: str
    query: str
    alt: Optional[str]
    start: int
    end: int


def find_markers(text: str) -> List[ImageMarker]:
    markers: List[ImageMarker] = []
    for match in MARKER_PATTERN.finditer(text):
        kind = match.group("kind").strip().upper()
        query = match.group("query").strip()
        alt = match.group("alt")
        if alt is not None:
            alt = alt.strip()
        markers.append(
            ImageMarker(
                kind=kind,
                query=query,
                alt=alt,
                start=match.start(),
                end=match.end(),
            )
        )
    return markers


def iter_markdown_files(vault_path: Path) -> Iterable[Path]:
    return (p for p in vault_path.rglob("*.md") if p.is_file())


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_note(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")

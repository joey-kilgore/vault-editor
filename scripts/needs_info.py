from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from vault_editor.config import load_config
from vault_editor.images import (
    download_image,
    get_tmdb_watch_providers,
    search_open_library_isbn,
    search_open_library_isbn_by_title,
    search_tmdb_poster,
    search_tmdb_movie_id,
)
from vault_editor.notes import iter_markdown_files, read_note, write_note

NEEDSINFO_TAG = "needsinfo"
BOOK_TAG = "book"
MOVIE_TAG = "movie"


def split_frontmatter(text: str) -> Tuple[Dict[str, Any] | None, str, str | None]:
    if not text.startswith("---\n"):
        return None, text, None

    lines = text.splitlines(keepends=True)
    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None, text, None

    fm_text = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    fm = yaml.safe_load(fm_text) or {}
    return fm, body, fm_text


def dump_frontmatter(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        default_style='"',
    ).strip()


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def parse_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_tag(str(v)) for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,\s]+", value)
        return [normalize_tag(p) for p in parts if p.strip()]
    return []


def set_tags(value: Any, tags: list[str]) -> Any:
    if isinstance(value, list):
        return tags
    if isinstance(value, str):
        return ", ".join(tags)
    return tags


def has_inline_tag(text: str, tag: str) -> bool:
    return re.search(rf"(?<!\S)#{re.escape(tag)}\b", text, re.IGNORECASE) is not None


def remove_inline_tag(text: str, tag: str) -> str:
    return re.sub(rf"(?<!\S)#{re.escape(tag)}\b", "", text, flags=re.IGNORECASE)


def backup_note(note_path: Path, vault_path: Path, backup_root: Path) -> Path:
    relative = note_path.relative_to(vault_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_root / f"{relative.as_posix()}.{timestamp}.bak"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(note_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def confirm(prompt: str) -> bool:
    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def process_note(
    note_path: Path,
    vault_path: Path,
    backup_root: Path,
    attachments_dir: Path,
    tmdb_api_key: str,
    tmdb_region: str,
    apply: bool,
    yes: bool,
) -> bool:
    text = read_note(note_path)
    fm, body, _ = split_frontmatter(text)

    if fm is None:
        fm = {}
        body = text

    tags_value = fm.get("tags") or fm.get("tag")
    tags = parse_tags(tags_value)

    has_needsinfo = NEEDSINFO_TAG in tags or has_inline_tag(body, NEEDSINFO_TAG)
    if not has_needsinfo:
        return False

    has_book = BOOK_TAG in tags or has_inline_tag(body, BOOK_TAG)
    has_movie = MOVIE_TAG in tags or has_inline_tag(body, MOVIE_TAG)

    if has_book == has_movie:
        print(f"Skip ambiguous tags: {note_path}")
        return False

    updated = False

    if has_book:
        title = fm.get("title") or fm.get("Title") or note_path.stem
        author = fm.get("author") or fm.get("Author")
        isbn = search_open_library_isbn_by_title(
            str(title), str(author) if author else None
        )
        if isbn:
            fm["ISBN"] = str(isbn)
            cover = search_open_library_isbn(str(isbn))
            if cover:
                image_path = download_image(cover, attachments_dir)
                rel_path = image_path.relative_to(vault_path).as_posix()
                fm["Image"] = f"[[{rel_path}]]"
            updated = True
        else:
            print(f"No ISBN found for: {note_path}")
            return False

    if has_movie:
        title = fm.get("title") or fm.get("Title") or note_path.stem
        movie_id = search_tmdb_movie_id(str(title), tmdb_api_key)
        if not movie_id:
            print(f"No TMDb match for: {note_path}")
            return False

        poster = search_tmdb_poster(str(title), tmdb_api_key)
        if poster:
            image_path = download_image(poster, attachments_dir)
            rel_path = image_path.relative_to(vault_path).as_posix()
            fm["Image"] = f"[[{rel_path}]]"

        providers = get_tmdb_watch_providers(
            "movie", movie_id, tmdb_api_key, tmdb_region
        )
        if providers:
            fm["Service"] = providers
        else:
            fm["Service"] = []
        fm["TMDB"] = str(movie_id)
        updated = True

    if updated:
        tags = [t for t in tags if t != NEEDSINFO_TAG]
        if tags_value is not None:
            fm["tags"] = set_tags(tags_value, tags)
        else:
            fm["tags"] = tags

        body = remove_inline_tag(body, NEEDSINFO_TAG)
        body = re.sub(r"\n{3,}", "\n\n", body)

        fm_text = dump_frontmatter(fm)
        new_text = f"---\n{fm_text}\n---\n{body}"

        if not apply:
            print(f"Planned update: {note_path}")
            return True

        if not yes and not confirm(f"Apply changes to this note?"):
            return False

        backup_note(note_path, vault_path, backup_root)
        write_note(note_path, new_text)
        print(f"Updated: {note_path}")
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Populate metadata for notes tagged #needsinfo and remove the tag."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to disk (otherwise dry-run).",
    )
    parser.add_argument(
        "--note",
        type=str,
        help="Relative path to a single note inside the vault.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config = load_config(repo_root)

    vault_path = config.vault_path
    attachments_dir = vault_path / config.attachments_dir
    backup_root = vault_path / config.backup_dir

    if args.note:
        notes = [vault_path / args.note]
    else:
        notes = list(iter_markdown_files(vault_path))

    total_changes = 0
    for note_path in notes:
        if not note_path.exists():
            continue

        if process_note(
            note_path,
            vault_path,
            backup_root,
            attachments_dir,
            config.tmdb_api_key,
            config.tmdb_region,
            args.apply,
            args.yes,
        ):
            total_changes += 1

    if total_changes == 0:
        print("No changes needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from vault_editor.config import load_config
from vault_editor.images import (
    download_image,
    generate_openai_image,
    search_tmdb_poster,
    search_tmdb_tv_poster,
    search_open_library_cover,
    search_open_library_isbn,
    search_wikimedia,
)
from vault_editor.notes import find_markers, iter_markdown_files, read_note, write_note


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


def build_replacement(
    image_path: Path,
    vault_path: Path,
    alt: str | None,
    quoted: bool,
    quote_char: str | None,
) -> str:
    rel_path = image_path.relative_to(vault_path).as_posix()
    if quoted:
        quote = quote_char or '"'
        return f"{quote}[[{rel_path}]]{quote}"
    if alt:
        rel_path_url = rel_path.replace(" ", "%20")
        return f"![{alt}]({rel_path_url})"
    return f"![[{rel_path}]]"


def process_note(
    note_path: Path,
    vault_path: Path,
    attachments_dir: Path,
    openai_api_key: str,
    tmdb_api_key: str,
) -> tuple[str, int, int]:
    original = read_note(note_path)
    markers = find_markers(original)
    if not markers:
        return original, 0, 0

    updated = original
    offset = 0
    replacements = 0
    for marker in markers:
        image_path: Path | None = None
        if marker.kind == "IMAGE":
            result = search_wikimedia(marker.query)
            if result:
                image_path = download_image(result, attachments_dir)
        elif marker.kind == "BOOK":
            result = search_open_library_cover(marker.query)
            if result:
                image_path = download_image(result, attachments_dir)
        elif marker.kind == "BOOKISBN":
            result = search_open_library_isbn(marker.query)
            if result:
                image_path = download_image(result, attachments_dir)
        elif marker.kind == "MOVIE":
            result = search_tmdb_poster(marker.query, tmdb_api_key)
            if result:
                image_path = download_image(result, attachments_dir)
        elif marker.kind == "TV":
            result = search_tmdb_tv_poster(marker.query, tmdb_api_key)
            if result:
                image_path = download_image(result, attachments_dir)
        elif marker.kind == "AIIMAGE":
            try:
                image_path = generate_openai_image(
                    marker.query, openai_api_key, attachments_dir
                )
            except Exception as exc:
                print(f"OpenAI image generation failed for '{marker.query}': {exc}")

        if not image_path:
            continue

        replacement = build_replacement(
            image_path,
            vault_path,
            marker.alt,
            marker.quoted,
            marker.quote_char,
        )
        replacements += 1

        start = marker.start + offset
        end = marker.end + offset
        updated = updated[:start] + replacement + updated[end:]
        offset += len(replacement) - (marker.end - marker.start)

    return updated, len(markers), replacements


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Insert images into Obsidian notes from <!-- IMAGE: ... --> markers."
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

    if not args.apply:
        print(f"Found {len(notes)} note(s) in vault scan:")
        for note_path in notes:
            try:
                rel_note = note_path.relative_to(vault_path).as_posix()
            except ValueError:
                rel_note = str(note_path)

            marker_flag = ""
            if note_path.exists():
                try:
                    marker_flag = " ***" if find_markers(read_note(note_path)) else ""
                except OSError:
                    marker_flag = ""

            print(f"- {rel_note}{marker_flag}")

    total_changes = 0
    for note_path in notes:
        if not note_path.exists():
            print(f"Skip missing: {note_path}")
            continue

        updated, marker_count, replacement_count = process_note(
            note_path,
            vault_path,
            attachments_dir,
            config.openai_api_key,
            config.tmdb_api_key,
        )
        if marker_count == 0:
            continue

        if replacement_count == 0:
            print(f"No images found for markers in: {note_path}")
            continue

        if updated == read_note(note_path):
            continue

        total_changes += 1
        print(f"\nPlanned update: {note_path}")

        if not args.apply:
            print("Dry-run: no files written.")
            continue

        if config.confirm_writes and not args.yes:
            if not confirm("Apply changes to this note?"):
                continue

        backup_path = backup_note(note_path, vault_path, backup_root)
        write_note(note_path, updated)
        print(f"Updated. Backup saved to: {backup_path}")

    if total_changes == 0:
        print("No changes needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

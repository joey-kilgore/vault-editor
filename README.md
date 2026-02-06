# Vault Editor

Small Python tools for working with an Obsidian vault.

## Setup
1. Install deps:
   - `pip install -r requirements.txt`
2. Update `secrets.json` with your vault path and preferences.

## Image insertion tool
This tool scans notes for image markers and replaces them with an image embed.

**Marker formats** (inside your note):

Wikimedia (general images):
```
<!-- IMAGE: golden retriever puppy -->
```

Open Library (book covers):
```
<!-- BOOK: The Hobbit -->
```

Open Library (book covers by ISBN):
```
<!-- BOOKISBN: 9780547928227 -->
```

TMDb (movie posters):
```
<!-- MOVIE: Top Gun Maverick -->
```

TMDb (TV posters):
```
<!-- TV: The Bear -->
```

OpenAI (image generation):
```
<!-- AIIMAGE: watercolor painting of a lighthouse at sunset -->
```

Optionally add alt text to any marker:
```
<!-- IMAGE: golden retriever puppy | Puppy playing in grass -->
```

### Run (dry-run by default)
```
python scripts/insert_images.py
```

### Apply changes
```
python scripts/insert_images.py --apply
```

### Limit to one note (relative to vault)
```
python scripts/insert_images.py --note "Notes/MyNote.md" --apply
```

## Backups
Each modified note is backed up to the `backup_dir` (see `secrets.json`) before changes are applied.

## Needs-info metadata tool
This tool finds notes tagged `#needsinfo` plus either `#book` or `#movie`, fills metadata, and removes `#needsinfo`.
It also downloads a cover/poster into your attachments folder and writes an `Image` frontmatter field as a wikilink.

### Book example
```
---
tags: [book, needsinfo]
title: "Letters to the Church"
---
```

### Movie example
```
---
tags: [movie, needsinfo]
title: "Top Gun Maverick"
---
```

### Run (dry-run by default)
```
python scripts/needs_info.py
```

### Apply changes
```
python scripts/needs_info.py --apply
```

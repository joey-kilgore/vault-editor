from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    vault_path: Path
    openai_api_key: str
    tmdb_api_key: str
    attachments_dir: str
    backup_dir: str
    confirm_writes: bool


def load_config(repo_root: Path) -> Config:
    secrets_path = repo_root / "secrets.json"
    if not secrets_path.exists():
        raise FileNotFoundError(
            "Missing secrets.json. Copy and fill the example config first."
        )

    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    vault_path = Path(data.get("vault_path", "")).expanduser()
    if not vault_path.exists():
        raise FileNotFoundError(
            f"Vault path not found: {vault_path}. Update secrets.json."
        )

    return Config(
        vault_path=vault_path,
        openai_api_key=data.get("openai_api_key", ""),
        tmdb_api_key=data.get("tmdb_api_key", ""),
        attachments_dir=data.get("attachments_dir", "attachments"),
        backup_dir=data.get("backup_dir", ".vault_backups"),
        confirm_writes=bool(data.get("confirm_writes", True)),
    )

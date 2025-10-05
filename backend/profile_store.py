"""Persistence layer for script profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from .models import ScriptProfile


class ProfileStore:
    """Handle loading and saving ScriptProfile objects."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".local/share/run_sh_manager"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._store_path = self.base_dir / "profiles.json"

    @property
    def store_path(self) -> Path:
        return self._store_path

    def load_profiles(self) -> List[ScriptProfile]:
        if not self._store_path.exists():
            return []
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup_path = self._store_path.with_suffix(".bak")
            backup_path.write_bytes(self._store_path.read_bytes())
            raise
        profiles = []
        for item in raw:
            profile = ScriptProfile.from_dict(item)
            profile.ensure_paths(self.base_dir)
            profiles.append(profile)
        return profiles

    def save_profiles(self, profiles: Iterable[ScriptProfile]) -> None:
        serializable: List[Dict] = []
        for profile in profiles:
            profile.ensure_paths(self.base_dir)
            serializable.append(profile.to_dict())
        temp_path = self._store_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self._store_path)

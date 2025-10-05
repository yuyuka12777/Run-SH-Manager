"""High-level manager coordinating profiles and process runners."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Callable, Dict, Iterable, List, Optional

from .models import ProcessState, ProcessStatus, ScriptProfile
from .process_runner import ProcessRunner
from .profile_store import ProfileStore


class ScriptManager:
    """Manage script profiles and their supervised processes."""

    def __init__(
        self,
        store: Optional[ProfileStore] = None,
    ) -> None:
        self.store = store or ProfileStore()
        self._lock = RLock()
        self._profiles: Dict[str, ScriptProfile] = {}
        self._runners: Dict[str, ProcessRunner] = {}
        self._statuses: Dict[str, ProcessStatus] = {}
        self._listeners: List[Callable[[ProcessStatus], None]] = []
        self._load_initial_profiles()

    # ------------------------------------------------------------------
    # Persistence and listeners
    # ------------------------------------------------------------------
    def _load_initial_profiles(self) -> None:
        profiles = self.store.load_profiles()
        for profile in profiles:
            self._register_profile(profile)

    def save(self) -> None:
        with self._lock:
            self.store.save_profiles(self._profiles.values())

    def register_listener(self, callback: Callable[[ProcessStatus], None]) -> None:
        self._listeners.append(callback)

    def _on_runner_update(self, status: ProcessStatus) -> None:
        with self._lock:
            self._statuses[status.name] = status
        for listener in self._listeners:
            listener(status)

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------
    def get_profiles(self) -> List[ScriptProfile]:
        with self._lock:
            return list(self._profiles.values())

    def add_profile(self, profile: ScriptProfile) -> None:
        with self._lock:
            if profile.name in self._profiles:
                raise ValueError(f"Profile '{profile.name}' already exists")
            self._register_profile(profile)
            self.save()

    def update_profile(self, name: str, new_profile: ScriptProfile) -> None:
        with self._lock:
            if name not in self._profiles:
                raise KeyError(f"Profile '{name}' not found")
            if new_profile.name != name and new_profile.name in self._profiles:
                raise ValueError(f"Profile '{new_profile.name}' already exists")
            runner = self._runners.get(name)
            was_running = runner.is_running() if runner else False
            if runner:
                runner.stop(force=False)
            self._profiles.pop(name)
            self._statuses.pop(name, None)
            self._runners.pop(name, None)
            self._register_profile(new_profile)
            if was_running and new_profile.enabled:
                self.start_profile(new_profile.name)
            self.save()

    def remove_profile(self, name: str) -> None:
        with self._lock:
            runner = self._runners.pop(name, None)
            if runner:
                runner.stop(force=False)
            self._profiles.pop(name, None)
            self._statuses.pop(name, None)
            self.save()

    def _register_profile(self, profile: ScriptProfile) -> None:
        profile.ensure_paths(self.store.base_dir)
        self._profiles[profile.name] = profile
        status = ProcessStatus(name=profile.name)
        self._statuses[profile.name] = status
        runner = ProcessRunner(profile, status_callback=self._on_runner_update)
        self._runners[profile.name] = runner

    # ------------------------------------------------------------------
    # Process control
    # ------------------------------------------------------------------
    def start_profile(self, name: str) -> None:
        with self._lock:
            profile = self._profiles.get(name)
            if not profile or not profile.enabled:
                return
            runner = self._runners[name]
            runner.start()

    def stop_profile(self, name: str, force: bool = False) -> None:
        with self._lock:
            runner = self._runners.get(name)
            if runner:
                runner.stop(force=force)

    def restart_profile(self, name: str) -> None:
        with self._lock:
            runner = self._runners.get(name)
            if runner:
                runner.restart()

    def start_auto_profiles(self) -> None:
        for profile in self.get_profiles():
            if profile.enabled and profile.auto_start:
                self.start_profile(profile.name)

    def stop_all(self) -> None:
        for name in list(self._runners.keys()):
            self.stop_profile(name)

    # ------------------------------------------------------------------
    # Status and monitoring
    # ------------------------------------------------------------------
    def get_status(self, name: str) -> Optional[ProcessStatus]:
        with self._lock:
            return self._statuses.get(name)

    def list_statuses(self) -> List[ProcessStatus]:
        with self._lock:
            return list(self._statuses.values())

    def get_resource_usage(self, name: str) -> Dict[str, float | int | None]:
        with self._lock:
            runner = self._runners.get(name)
        if not runner:
            return {"cpu_percent": None, "memory_mb": None}
        return runner.get_resource_usage()

    def ensure_log_directory(self) -> Path:
        logs_dir = self.store.base_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

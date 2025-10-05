"""Data models for run_sh_manager."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class ProcessState(str, Enum):
    """Lifecycle states for a managed script process."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"
    EXITED = "exited"
    FAILED = "failed"


@dataclass
class ScriptProfile:
    """Configuration profile for a script run."""

    name: str
    script_path: str
    working_dir: Optional[str] = None
    auto_start: bool = False
    restart_on_exit: bool = True
    restart_delay: float = 5.0
    start_delay: float = 0.0
    environment: Dict[str, str] = field(default_factory=dict)
    log_path: Optional[str] = None
    max_restarts: Optional[int] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptProfile":
        return cls(**data)

    def ensure_paths(self, base_dir: Path) -> None:
        """Ensure paths like log directory exist."""
        if not self.log_path:
            logs_dir = base_dir / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            safe_name = self.name.replace(" ", "_")
            self.log_path = str(logs_dir / f"{safe_name}.log")
        else:
            Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ProcessStatus:
    """Runtime status for a managed script."""

    name: str
    state: ProcessState = ProcessState.STOPPED
    pid: Optional[int] = None
    start_time: Optional[float] = None
    restarts: int = 0
    last_exit_code: Optional[int] = None
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "pid": self.pid,
            "start_time": self.start_time,
            "restarts": self.restarts,
            "last_exit_code": self.last_exit_code,
            "last_error": self.last_error,
        }

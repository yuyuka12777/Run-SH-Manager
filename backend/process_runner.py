"""Process supervision utilities."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

import psutil

from .models import ProcessState, ProcessStatus, ScriptProfile


class ProcessRunner:
    """Manage the lifecycle of a configured script process."""

    def __init__(
        self,
        profile: ScriptProfile,
        status_callback: Optional[Callable[[ProcessStatus], None]] = None,
    ) -> None:
        self.profile = profile
        self.status = ProcessStatus(name=profile.name)
        self._status_callback = status_callback
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._base_env = os.environ.copy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name=f"Runner-{self.profile.name}", daemon=True)
            self._thread.start()

    def stop(self, force: bool = False) -> None:
        self._stop_event.set()
        proc = self._process
        if proc and proc.poll() is None:
            self._terminate_process(proc, force=force)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        with self._lock:
            self._process = None
            self.status.state = ProcessState.STOPPED
            self.status.pid = None
            self._notify_status()

    def restart(self) -> None:
        self.stop()
        self.start()

    def is_running(self) -> bool:
        proc = self._process
        return proc is not None and proc.poll() is None

    def get_resource_usage(self) -> Dict[str, float | int | None]:
        proc = self._process
        if proc is None or proc.poll() is not None:
            return {"cpu_percent": None, "memory_mb": None}
        try:
            ps_proc = psutil.Process(proc.pid)
            cpu = ps_proc.cpu_percent(interval=0.0)
            mem = ps_proc.memory_info().rss / (1024 * 1024)
            return {"cpu_percent": cpu, "memory_mb": mem}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"cpu_percent": None, "memory_mb": None}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        restart_attempts = 0
        profile = self.profile
        self.status.restarts = 0
        if profile.start_delay > 0:
            time.sleep(profile.start_delay)
        while not self._stop_event.is_set():
            try:
                self._update_state(ProcessState.STARTING)
                process = self._launch_process()
                if process is None:
                    self._update_failure("Failed to launch process")
                    break
                self._process = process
                self.status.pid = process.pid
                self.status.start_time = time.time()
                self._update_state(ProcessState.RUNNING)
                return_code = process.wait()
                self.status.last_exit_code = return_code
                self.status.pid = None
                if self._stop_event.is_set():
                    self._update_state(ProcessState.STOPPED)
                    break
                if not profile.restart_on_exit:
                    self._update_state(ProcessState.EXITED)
                    break
                restart_attempts += 1
                self.status.restarts = restart_attempts
                if profile.max_restarts is not None and restart_attempts > profile.max_restarts:
                    self._update_failure("Reached max restart attempts")
                    break
                self._update_state(ProcessState.RESTARTING)
                if profile.restart_delay > 0:
                    waited = 0.0
                    while waited < profile.restart_delay and not self._stop_event.is_set():
                        time.sleep(min(0.5, profile.restart_delay - waited))
                        waited += 0.5
                continue
            except Exception as exc:  # pylint: disable=broad-except
                self._update_failure(str(exc))
                break
        self._process = None

    def _launch_process(self) -> Optional[subprocess.Popen]:
        profile = self.profile
        script_path = Path(profile.script_path).expanduser()
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        log_path = Path(profile.log_path) if profile.log_path else None
        log_file = subprocess.DEVNULL
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_path, "ab", buffering=0)
        try:
            env = self._base_env.copy()
            env.update(profile.environment)
            command = ["/bin/bash", str(script_path)]
            if os.access(script_path, os.X_OK) and script_path.is_file():
                # Allow executable scripts without forcing bash.
                command = [str(script_path)]
            process = subprocess.Popen(
                command,
                cwd=profile.working_dir or str(script_path.parent),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            return process
        finally:
            if hasattr(log_file, "close"):
                # Keep the file open by the subprocess; close the handle in parent.
                log_file.close()

    def _update_state(self, state: ProcessState) -> None:
        self.status.state = state
        self._notify_status()

    def _update_failure(self, error: str) -> None:
        self.status.state = ProcessState.FAILED
        self.status.last_error = error
        self._notify_status()

    def _notify_status(self) -> None:
        callback = self._status_callback
        if callback:
            try:
                callback(self.status)
            except Exception:  # pragma: no cover - avoid crashes in callbacks
                pass

    # ------------------------------------------------------------------
    # Process termination helpers
    # ------------------------------------------------------------------
    def _terminate_process(self, process: subprocess.Popen, force: bool) -> None:
        """Send termination signals to the process (and its children)."""

        if self._send_signal(process, signal.SIGTERM):
            if self._wait_for_exit(process, timeout=10):
                return

        if force or process.poll() is None:
            # Give the process group a last chance before force killing.
            self._send_signal(process, signal.SIGINT)
            if self._wait_for_exit(process, timeout=5):
                return
            self._send_signal(process, signal.SIGKILL)
            self._wait_for_exit(process, timeout=5)

    def _send_signal(self, process: subprocess.Popen, sig: int) -> bool:
        """Send *sig* either to the process group (preferred) or the process itself."""

        sent = False
        try:
            if hasattr(os, "killpg"):
                os.killpg(process.pid, sig)
                sent = True
        except ProcessLookupError:
            return True
        except PermissionError:
            pass

        if not sent:
            try:
                process.send_signal(sig)
                sent = True
            except ProcessLookupError:
                return True
            except Exception:
                return False
        return sent

    @staticmethod
    def _wait_for_exit(process: subprocess.Popen, timeout: float) -> bool:
        try:
            process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

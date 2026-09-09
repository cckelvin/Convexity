"""
Convexity Process Manager
Version: 0.9.0

Unified process abstraction for Convexity.

Responsibilities:
- Start normal processes
- Start interactive PTY processes
- Track processes
- Capture output
- Wait for completion
- Terminate processes
- Kill processes
- Send signals where supported
- Expose process information to the shell and Maple

Architecture:

    Shell / Maple
          |
          v
    ProcessManager
       /       \
      v         v
  Normal     Interactive
  Process       PTY
      \         /
       \       /
        Process
          |
          v
      Operating System
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Sequence, Any

from .pty_platform import (
    create_pty,
    is_pty_supported,
    get_pty_backend_name,
)


__version__ = "0.9.0"


# ---------------------------------------------------------------------------
# Process state
# ---------------------------------------------------------------------------

class ProcessState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"
    KILLED = "killed"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Process information
# ---------------------------------------------------------------------------

@dataclass
class ProcessInfo:
    """
    Public information about a Convexity process.
    """

    process_id: int

    command: str

    state: ProcessState = ProcessState.CREATED

    return_code: Optional[int] = None

    pid: Optional[int] = None

    interactive: bool = False

    pty_backend: Optional[str] = None

    background: bool = False

    cwd: Optional[str] = None

    started_at: Optional[float] = None

    finished_at: Optional[float] = None

    stdout: str = ""

    stderr: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Managed process
# ---------------------------------------------------------------------------

class ManagedProcess:

    def __init__(
        self,
        process_id: int,
        command: Sequence[str],
        *,
        interactive: bool = False,
        background: bool = False,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        callback: Optional[
            Callable[[str], None]
        ] = None,
    ):

        self.process_id = process_id

        self.command_args = list(command)

        self.command = " ".join(
            self.command_args
        )

        self.interactive = interactive

        self.background = background

        self.cwd = cwd

        self.env = env

        self.callback = callback

        self.state = ProcessState.CREATED

        self.return_code: Optional[int] = None

        self.pid: Optional[int] = None

        self.pty = None

        self.subprocess: Optional[
            subprocess.Popen
        ] = None

        self.started_at: Optional[float] = None

        self.finished_at: Optional[float] = None

        self._stdout = bytearray()

        self._stderr = bytearray()

        self._lock = threading.RLock()

        self._reader_threads: list[
            threading.Thread
        ] = []

    # -----------------------------------------------------------------------
    # Start
    # -----------------------------------------------------------------------

    def start(self) -> "ManagedProcess":

        if self.state != ProcessState.CREATED:
            raise RuntimeError(
                "Process has already been started."
            )

        self.started_at = time.time()

        if self.interactive:

            self._start_pty()

        else:

            self._start_normal()

        return self

    # -----------------------------------------------------------------------
    # Normal process
    # -----------------------------------------------------------------------

    def _start_normal(self) -> None:

        try:

            self.subprocess = subprocess.Popen(
                self.command_args,
                cwd=self.cwd,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                text=False,
            )

        except Exception:

            self.state = ProcessState.FAILED

            self.finished_at = time.time()

            raise

        self.pid = self.subprocess.pid

        self.state = ProcessState.RUNNING

        stdout_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True,
        )

        stderr_thread = threading.Thread(
            target=self._read_stderr,
            daemon=True,
        )

        self._reader_threads.extend(
            [
                stdout_thread,
                stderr_thread,
            ]
        )

        stdout_thread.start()
        stderr_thread.start()

        if self.background:

            monitor = threading.Thread(
                target=self._monitor_normal,
                daemon=True,
            )

            monitor.start()

    # -----------------------------------------------------------------------
    # PTY process
    # -----------------------------------------------------------------------

    def _start_pty(self) -> None:

        if not is_pty_supported():
            raise RuntimeError(
                "Interactive PTY processes are not "
                "supported on this platform."
            )

        self.pty = create_pty(
            self.command_args,
            cwd=self.cwd,
            env=self.env,
            callback=self._handle_pty_output,
        )

        self.pid = getattr(
            self.pty,
            "child_pid",
            None,
        )

        if self.pid is None:

            self.pid = getattr(
                self.pty,
                "process_id",
                None,
            )

        self.state = ProcessState.RUNNING

        if self.background:

            monitor = threading.Thread(
                target=self._monitor_pty,
                daemon=True,
            )

            monitor
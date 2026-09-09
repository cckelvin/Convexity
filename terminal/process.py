"""
Convexity Process Manager
Version: 0.9.1

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

This module is the single process-management layer.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Sequence

from .pty_platform import (
    create_pty,
    is_pty_supported,
    get_pty_backend_name,
)


__version__ = "0.9.1"


# ---------------------------------------------------------------------------
# PROCESS STATE
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
# PROCESS INFORMATION
# ---------------------------------------------------------------------------

@dataclass
class ProcessInfo:
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

    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MANAGED PROCESS
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
        callback: Optional[Callable[[str], None]] = None,
    ) -> None:

        if not command:
            raise ValueError("Process command cannot be empty.")

        self.process_id = process_id
        self.command_args = list(command)
        self.command = " ".join(self.command_args)

        self.interactive = interactive
        self.background = background

        self.cwd = cwd
        self.env = env
        self.callback = callback

        self.state = ProcessState.CREATED
        self.return_code: Optional[int] = None
        self.pid: Optional[int] = None

        self.pty = None
        self.subprocess: Optional[subprocess.Popen] = None

        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        self._stdout = bytearray()
        self._stderr = bytearray()

        self._lock = threading.RLock()
        self._reader_threads: list[threading.Thread] = []

    # -----------------------------------------------------------------------
    # START
    # -----------------------------------------------------------------------

    def start(self) -> "ManagedProcess":

        with self._lock:

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
    # NORMAL PROCESS
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
            [stdout_thread, stderr_thread]
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
    # PTY PROCESS
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

            monitor.start()

    # -----------------------------------------------------------------------
    # OUTPUT READERS
    # -----------------------------------------------------------------------

    def _read_stdout(self) -> None:

        if self.subprocess is None:
            return

        stream = self.subprocess.stdout

        if stream is None:
            return

        try:

            while True:

                data = stream.read(4096)

                if not data:
                    break

                with self._lock:
                    self._stdout.extend(data)

                if self.callback:

                    try:
                        self.callback(
                            data.decode(
                                "utf-8",
                                errors="replace",
                            )
                        )
                    except Exception:
                        pass

        except (OSError, ValueError):
            pass

    def _read_stderr(self) -> None:

        if self.subprocess is None:
            return

        stream = self.subprocess.stderr

        if stream is None:
            return

        try:

            while True:

                data = stream.read(4096)

                if not data:
                    break

                with self._lock:
                    self._stderr.extend(data)

        except (OSError, ValueError):
            pass

    def _handle_pty_output(self, output: str) -> None:

        if not output:
            return

        with self._lock:

            self._stdout.extend(
                output.encode(
                    "utf-8",
                    errors="replace",
                )
            )

        if self.callback:

            try:
                self.callback(output)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # MONITORS
    # -----------------------------------------------------------------------

    def _monitor_normal(self) -> None:

        if self.subprocess is None:
            return

        try:

            return_code = self.subprocess.wait()

            with self._lock:

                self.return_code = return_code
                self.finished_at = time.time()

                if self.state == ProcessState.RUNNING:

                    if return_code == 0:
                        self.state = ProcessState.COMPLETED
                    else:
                        self.state = ProcessState.FAILED

        except Exception:

            with self._lock:

                self.state = ProcessState.UNKNOWN
                self.finished_at = time.time()

    def _monitor_pty(self) -> None:

        try:

            result = self.pty.wait()

            return_code = getattr(
                result,
                "return_code",
                None,
            )

            with self._lock:

                self.return_code = return_code
                self.finished_at = time.time()

                if self.state == ProcessState.RUNNING:

                    if return_code in (None, 0):
                        self.state = ProcessState.COMPLETED
                    else:
                        self.state = ProcessState.FAILED

        except Exception:

            with self._lock:

                self.state = ProcessState.UNKNOWN
                self.finished_at = time.time()

    # -----------------------------------------------------------------------
    # WAIT
    # -----------------------------------------------------------------------

    def wait(
        self,
        timeout: Optional[float] = None,
    ) -> int:

        if self.interactive:

            if self.pty is None:
                raise RuntimeError(
                    "PTY process has not been started."
                )

            result = self.pty.wait(timeout=timeout)

            self.return_code = getattr(
                result,
                "return_code",
                None,
            )

        else:

            if self.subprocess is None:
                raise RuntimeError(
                    "Process has not been started."
                )

            self.return_code = self.subprocess.wait(
                timeout=timeout
            )

        with self._lock:

            self.finished_at = time.time()

            if self.state == ProcessState.RUNNING:

                if self.return_code == 0:
                    self.state = ProcessState.COMPLETED
                else:
                    self.state = ProcessState.FAILED

        return (
            self.return_code
            if self.return_code is not None
            else -1
        )

    # -----------------------------------------------------------------------
    # POLL
    # -----------------------------------------------------------------------

    def poll(self) -> Optional[int]:

        if self.interactive:

            if self.pty is None:
                return None

            process = getattr(
                self.pty,
                "process",
                None,
            )

            if process is None:
                return None

            return process.poll()

        if self.subprocess is None:
            return None

        result = self.subprocess.poll()

        if result is not None:

            with self._lock:

                self.return_code = result
                self.finished_at = (
                    self.finished_at
                    or time.time()
                )

                if self.state == ProcessState.RUNNING:

                    if result == 0:
                        self.state = ProcessState.COMPLETED
                    else:
                        self.state = ProcessState.FAILED

        return result

    # -----------------------------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------------------------

    def stdout(self) -> str:

        with self._lock:

            return self._stdout.decode(
                "utf-8",
                errors="replace",
            )

    def stderr(self) -> str:

        with self._lock:

            return self._stderr.decode(
                "utf-8",
                errors="replace",
            )

    # -----------------------------------------------------------------------
    # INPUT
    # -----------------------------------------------------------------------

    def write(self, data: str) -> None:

        if self.interactive:

            if self.pty is None:
                raise RuntimeError(
                    "PTY process has not been started."
                )

            self.pty.write(data)
            return

        if self.subprocess is None:
            raise RuntimeError(
                "Process has not been started."
            )

        if self.subprocess.stdin is None:
            raise RuntimeError(
                "Process stdin is unavailable."
            )

        try:

            self.subprocess.stdin.write(
                data.encode("utf-8")
            )

            self.subprocess.stdin.flush()

        except (BrokenPipeError, OSError):
            pass

    # -----------------------------------------------------------------------
    # TERMINATE
    # -----------------------------------------------------------------------

    def terminate(self) -> bool:

        if self.poll() is not None:
            return True

        try:

            if self.interactive:

                if self.pty is not None:
                    self.pty.terminate()

            elif self.subprocess is not None:

                self.subprocess.terminate()

            self.state = ProcessState.TERMINATED

            return True

        except (OSError, RuntimeError):

            return False

    # -----------------------------------------------------------------------
    # KILL
    # -----------------------------------------------------------------------

    def kill(self) -> bool:

        if self.poll() is not None:
            return True

        try:

            if self.interactive:

                if self.pty is not None:
                    self.pty.kill()

            elif self.subprocess is not None:

                self.subprocess.kill()

            self.state = ProcessState.KILLED

            return True

        except (OSError, RuntimeError):

            return False

    # -----------------------------------------------------------------------
    # SIGNAL
    # -----------------------------------------------------------------------

    def send_signal(self, sig: int) -> bool:

        if self.poll() is not None:
            return False

        try:

            if self.interactive:

                if self.pty is not None:

                    sender = getattr(
                        self.pty,
                        "send_signal",
                        None,
                    )

                    if callable(sender):
                        sender(sig)
                        return True

            if self.subprocess is not None:

                self.subprocess.send_signal(sig)
                return True

        except (OSError, RuntimeError):

            return False

        return False

    # -----------------------------------------------------------------------
    # INFO
    # -----------------------------------------------------------------------

    def info(self) -> ProcessInfo:

        backend = None

        if self.interactive:

            try:
                backend = get_pty_backend_name()
            except Exception:
                backend = None

        return ProcessInfo(
            process_id=self.process_id,
            command=self.command,
            state=self.state,
            return_code=self.return_code,
            pid=self.pid,
            interactive=self.interactive,
            pty_backend=backend,
            background=self.background,
            cwd=self.cwd,
            started_at=self.started_at,
            finished_at=self.finished_at,
            stdout=self.stdout(),
            stderr=self.stderr(),
        )


# ---------------------------------------------------------------------------
# PROCESS MANAGER
# ---------------------------------------------------------------------------

class ProcessManager:

    def __init__(self) -> None:

        self._processes: dict[int, ManagedProcess] = {}

        self._lock = threading.RLock()

        self._next_id = 1

    # -----------------------------------------------------------------------
    # CREATE
    # -----------------------------------------------------------------------

    def create(
        self,
        command: Sequence[str],
        *,
        interactive: bool = False,
        background: bool = False,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ManagedProcess:

        with self._lock:

            process_id = self._next_id
            self._next_id += 1

            process = ManagedProcess(
                process_id,
                command,
                interactive=interactive,
                background=background,
                cwd=cwd,
                env=env,
                callback=callback,
            )

            self._processes[process_id] = process

        return process

    # -----------------------------------------------------------------------
    # START
    # -----------------------------------------------------------------------

    def start(
        self,
        command: Sequence[str],
        *,
        interactive: bool = False,
        background: bool = False,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ManagedProcess:

        process = self.create(
            command,
            interactive=interactive,
            background=background,
            cwd=cwd,
            env=env,
            callback=callback,
        )

        try:

            process.start()

        except Exception:

            with self._lock:
                self._processes.pop(
                    process.process_id,
                    None,
                )

            raise

        return process

    # -----------------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------------

    def get(
        self,
        process_id: int,
    ) -> Optional[ManagedProcess]:

        with self._lock:
            return self._processes.get(process_id)

    # -----------------------------------------------------------------------
    # LIST
    # -----------------------------------------------------------------------

    def list(
        self,
        *,
        include_finished: bool = True,
    ) -> list[ProcessInfo]:

        with self._lock:

            processes = list(
                self._processes.values()
            )

        result = []

        for process in processes:

            if (
                not include_finished
                and process.poll() is not None
            ):
                continue

            result.append(
                process.info()
            )

        return result

    # -----------------------------------------------------------------------
    # REMOVE FINISHED
    # -----------------------------------------------------------------------

    def remove_finished(self) -> None:

        with self._lock:

            finished = []

            for process_id, process in self._pr
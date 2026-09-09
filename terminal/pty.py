"""
Convexity PTY / Interactive Process Layer
Version: 0.8.0

Provides a platform-independent interface for running interactive
terminal programs.

Architecture:

    Convexity Shell
          |
          v
       PTYSession
          |
    +-----+-----+
    |           |
   Unix       Windows
    PTY       ConPTY
    |           |
    +-----+-----+
          |
          v
     Interactive
      Process

This module intentionally does NOT depend on Bash, PowerShell,
CMD, Termux, or another terminal application.

Platform-specific implementations can be added later while
keeping the public PTYSession API stable.
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Sequence


__version__ = "0.8.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PTYError(Exception):
    """Base exception for PTY-related errors."""


class PTYNotSupportedError(PTYError):
    """Raised when interactive PTY support is unavailable."""


class PTYProcessError(PTYError):
    """Raised when a PTY process cannot be started or controlled."""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class PTYState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    KILLED = "killed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class PTYResult:
    """Result information from an interactive process."""

    return_code: Optional[int] = None
    state: PTYState = PTYState.CREATED
    output: str = ""
    error: str = ""
    duration: float = 0.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PTYConfig:
    """Configuration for an interactive PTY session."""

    cwd: Optional[str] = None

    env: Optional[dict[str, str]] = None

    columns: int = 120
    rows: int = 30

    encoding: str = "utf-8"

    errors: str = "replace"

    startup_timeout: float = 10.0

    read_chunk_size: int = 4096

    combine_output: bool = True

    auto_flush: bool = True

    create_process_group: bool = True


# ---------------------------------------------------------------------------
# PTY session
# ---------------------------------------------------------------------------

class PTYSession:
    """
    Cross-platform interactive process session.

    The current implementation provides a stable abstraction and
    a Unix PTY backend using Python's standard library.

    Windows ConPTY and Android-specific implementations can be
    connected behind this same API later.
    """

    def __init__(
        self,
        command: Sequence[str],
        config: Optional[PTYConfig] = None,
    ):
        if not command:
            raise ValueError("PTY command cannot be empty.")

        self.command = list(command)
        self.config = config or PTYConfig()

        self.process: Optional[subprocess.Popen] = None

        self.state = PTYState.CREATED

        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        self._output = bytearray()
        self._output_lock = threading.Lock()

        self._reader_thread: Optional[threading.Thread] = None

        self._stop_reader = threading.Event()

        self._output_callback: Optional[Callable[[str], None]] = None

        self._pty_master = None

        self._lock = threading.RLock()

    # -----------------------------------------------------------------------
    # Platform
    # -----------------------------------------------------------------------

    @staticmethod
    def platform_name() -> str:
        """Return the current operating-system family."""

        system = platform.system().lower()

        if system == "windows":
            return "windows"

        if system == "darwin":
            return "macos"

        if system == "linux":
            return "linux"

        if "android" in platform.platform().lower():
            return "android"

        return system

    # -----------------------------------------------------------------------
    # Support
    # -----------------------------------------------------------------------

    @classmethod
    def is_supported(cls) -> bool:
        """
        Return whether the standard-library PTY backend is available.

        Unix-like systems normally provide the required PTY module.
        Windows requires a future ConPTY backend.
        """

        if os.name == "posix":
            try:
                import pty  # noqa: F401
                return True
            except ImportError:
                return False

        return False

    # -----------------------------------------------------------------------
    # Start
    # -----------------------------------------------------------------------

    def start(
        self,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> "PTYSession":
        """Start the interactive process."""

        with self._lock:
            if self.state not in (
                PTYState.CREATED,
                PTYState.FAILED,
            ):
                raise PTYProcessError(
                    f"Cannot start PTY from state: {self.state.value}"
                )

            self.state = PTYState.STARTING

            self._output_callback = output_callback

            self.started_at = time.time()

        if os.name == "posix":
            self._start_unix()

        elif os.name == "nt":
            self._start_windows()

        else:
            self.state = PTYState.FAILED
            raise PTYNotSupportedError(
                f"PTY is not yet implemented for platform: {os.name}"
            )

        return self

    # -----------------------------------------------------------------------
    # Unix backend
    # -----------------------------------------------------------------------

    def _start_unix(self) -> None:
        """Start a process attached to a Unix PTY."""

        try:
            import pty
            import fcntl
            import struct
            import termios

            master_fd, slave_fd = pty.openpty()

            self._pty_master = master_fd

            # Configure terminal size.
            winsize = struct.pack(
                "HHHH",
                self.config.rows,
                self.config.columns,
                0,
                0,
            )

            try:
                fcntl.ioctl(
                    slave_fd,
                    termios.TIOCSWINSZ,
                    winsize,
                )
            except Exception:
                pass

            preexec_fn = None

            if self.config.create_process_group:

                def create_process_group() -> None:
                    os.setsid()

                preexec_fn = create_process_group

            self.process = subprocess.Popen(
                self.command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.config.cwd,
                env=self.config.env,
                preexec_fn=preexec_fn,
                close_fds=True,
            )

            os.close(slave_fd)

            self.state = PTYState.RUNNING

            self._start_reader()

        except Exception as exc:
            try:
                os.close(self._pty_master)
            except Exception:
                pass

            self._pty_master = None

            self.state = PTYState.FAILED

            raise PTYProcessError(
                f"Failed to start Unix PTY: {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Windows backend
    # -----------------------------------------------------------------------

    def _start_windows(self) -> None:
        """
        Windows interactive backend.

        A real implementation will use Windows ConPTY.

        We deliberately do not silently fall back to CMD or PowerShell,
        because Convexity must remain independent of those shells.
        """

        self.state = PTYState.FAILED

        raise PTYNotSupportedError(
            "Windows ConPTY backend is not implemented yet. "
            "Use the future terminal/pty_windows.py backend."
        )

    # -----------------------------------------------------------------------
    # Reader
    # -----------------------------------------------------------------------

    def _start_reader(self) -> None:
        """Start the background PTY output reader."""

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="Convexity-PTY-Reader",
            daemon=True,
        )

        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Continuously read data from the PTY."""

        if self._pty_master is None:
            return

        while not self._stop_reader.is_set():

            try:
                data = os.read(
                    self._pty_master,
                    self.config.read_chunk_size,
                )

            except OSError:
                break

            except Exception:
                break

            if not data:
                break

            with self._output_lock:
                self._output.extend(data)

            text = data.decode(
                self.config.encoding,
                errors=self.config.errors,
            )

            if self._output_callback is not None:
                try:
                    self._output_callback(text)
                except Exception:
                    pass

        self._finish_state()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def write(self, data: str | bytes) -> None:
        """
        Send input to the interactive process.

        This is the mechanism Convexity will eventually use for:

        - typing commands
        - interactive prompts
        - REPLs
        - editors
        - Python shells
        - Git prompts
        - full-screen terminal applications
        """

        if self._pty_master is None:
            raise PTYProcessError("PTY session is not running.")

        if isinstance(data, str):
            data = data.encode(
                self.config.encoding,
                errors=self.config.errors,
            )

        try:
            os.write(self._pty_master, data)
        except OSError as exc:
            raise PTYProcessError(
                f"Failed to write to PTY: {exc}"
            ) from exc

    def send_line(self, text: str) -> None:
        """Send text followed by Enter."""

        self.write(text + "\n")

    # -----------------------------------------------------------------------
    # Terminal control
    # -----------------------------------------------------------------------

    def send_ctrl_c(self) -> None:
        """Send an interrupt signal to the process."""

        if self.process is None:
            return

        if os.name == "posix":

            try:
                if self.config.create_process_group:
                    os.killpg(
                        os.getpgid(self.process.pid),
                        signal.SIGINT,
                    )
                else:
                    self.process.send_signal(signal.SIGINT)

            except ProcessLookupError:
                pass

        elif os.name == "nt":
            raise PTYNotSupportedError(
                "Windows Ctrl+C requires the ConPTY backend."
            )

    def send_ctrl_z(self) -> None:
        """Suspend the process on Unix systems."""

        if os.name != "posix":
            raise PTYNotSupportedError(
                "Ctrl+Z job control is not available on this platform yet."
            )

        if self.process is None:
            return

        try:
            if self.config.create_process_group:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGTSTP,
                )
            else:
                self.process.send_signal(signal.SIGTSTP)

            self.state = PTYState.STOPPED

        except ProcessLookupError:
            pass

    # -----------------------------------------------------------------------
    # Resize
    # -----------------------------------------------------------------------

    def resize(
        self,
        columns: int,
        rows: int,
    ) -> None:
        """
        Resize the virtual terminal.

        This is required for terminal applications such as editors,
        pagers, REPLs and full-screen applications.
        """

        if columns <= 0 or rows <= 0:
            raise ValueError(
                "Terminal dimensions must be positive."
            )

        self.config.columns = columns
        self.config.rows = rows

        if os.name != "posix":
            raise PTYNotSupportedError(
                "PTY resizing for this platform is not implemented yet."
            )

        if self._pty_master is None:
            return

        import fcntl
        import struct
        import termios

        winsize = struct.pack(
            "HHHH",
            rows,
            columns,
            0,
            0,
        )

        try:
            fcntl.ioctl(
                self._pty_master,
                termios.TIOCSWINSZ,
                winsize,
            )
        except Exception as exc:
            raise PTYError(
                f"Failed to resize PTY: {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------

    def get_output(self) -> str:
        """Return all captured output."""

        with self._output_lock:
            data = bytes(self._output)

        return data.decode(
            self.config.encoding,
            errors=self.config.errors,
        )

    def clear_output(self) -> None:
        """Clear the captured output buffer."""

        with self._output_lock:
            self._output.clear()

    # -----------------------------------------------------------------------
    # Process status
    # -----------------------------------------------------------------------

    def poll(self) -> Optional[int]:
        """Return the process return code if finished."""

        if self.process is None:
            return None

        return self.process.poll()

    def is_running(self) -> bool:
        """Return whether the process is still running."""

        return (
            self.process is not None
            and self.process.poll() is None
        )

    # -----------------------------------------------------------------------
    # Wait
    # -----------------------------------------------------------------------

    def wait(
        self,
        timeout: Optional[float] = None,
    ) -> PTYResult:
        """Wait for the process to finish."""

        if self.process is None:
            raise PTYProcessError("PTY process has not started.")

        try:
            return_code = self.process.wait(timeout=timeout)

        except subprocess.TimeoutExpired as exc:
            raise PTYProcessError(
                "PTY process did not finish before the timeout."
            ) from exc

        self._finish_state(return_code)

        duration = 0.0

        if self.started_at is not None:
            duration = time.time() - self.started_at

        return PTYResult(
            return_code=return_code,
            state=self.state,
            output=self.get_output(),
            duration=duration,
        )

    # -----------------------------------------------------------------------
    # Termination
    # -----------------------------------------------------------------------

    def terminate(self) -> None:
        """Request graceful process termination."""

        if self.process is None:
            return

        try:
            if os.name == "posix" and self.config.create_process_group:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGTERM,
                )
            else:
                self.process.terminate()

            self.state = PTYState.TERMINATED

        except ProcessLookupError:
            pass

    def kill(self) -> None:
        """Forcefully terminate the process."""

        if self.process is None:
            return

        try:
            if os.name == "posix" and self.config.create_process_group:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGKILL,
                )
            else:
                self.process.kill()

            self.state = PTYState.KILLED

        except ProcessLookupError:
            pass

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def close(self) -> None:
        """Close the PTY session."""

        self._stop_reader.set()

        if self.process is not None:
            if self.is_running():
                self.terminate()

        if self._pty_master is not None:
            try:
                os.close(self._pty_master)
            except OSError:
                pass

            self._pty_master = None

        self._finish_state()

    # -----------------------------------------------------------------------
    # Internal state
    # -----------------------------------------------------------------------

    def _finish_state(
        self,
        return_code: Optional[int] = None,
    ) -> None:

        if self.finished_at is None:
            self.finished_at = time.time()

        if return_code is None and self.process is not None:
            return_code = self.process.poll()

        if return_code is None:
            return

        if self.state in (
            PTYState.TERMINATED,
            PTYState.KILLED,
        ):
            return

        if return_code == 0:
            self.state = PTYState.COMPLETED
        else:
            self.state = PTYState.FAILED

    # -----------------------------------------------------------------------
    # Context manager
    # -----------------------------------------------------------------------

    def __enter__(self) -> "PTYSession":
        self.start()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_pty(
    command: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    columns: int = 120,
    rows: int = 30,
    output_callback: Optional[Callable[[str], None]] = None,
) -> PTYSession:
    """
    Create and start a PTY session.

    Example:

        session = create_pty(["python"])

        session.send_line("print(2 + 2)")

        session.wait()
    """

    config = PTYConfig(
        cwd=cwd,
 
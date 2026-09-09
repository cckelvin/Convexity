"""
Convexity Unix PTY Backend
Version: 0.8.1

Low-level Unix implementation for Convexity's interactive terminal.

Supported platforms:
- Linux
- macOS
- Other POSIX systems with PTY support

This module does not invoke Bash, PowerShell, CMD, or Termux.
It directly attaches processes to a Unix pseudo-terminal.
"""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import termios
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


__version__ = "0.8.1"


class UnixPTYError(Exception):
    """Base Unix PTY error."""


class UnixPTYClosedError(UnixPTYError):
    """Raised when a PTY is already closed."""


@dataclass
class UnixPTYConfig:
    """Configuration for a Unix PTY."""

    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None

    columns: int = 120
    rows: int = 30

    encoding: str = "utf-8"
    errors: str = "replace"

    read_size: int = 4096

    create_session: bool = True


class UnixPTY:
    """
    Direct Unix pseudo-terminal session.

    The PTY consists of:

        Convexity
            |
            v
        PTY master
            |
        PTY slave
            |
            v
        Child process

    The master remains controlled by Convexity.
    """

    def __init__(
        self,
        command: Sequence[str],
        config: Optional[UnixPTYConfig] = None,
    ):
        if not command:
            raise ValueError("Command cannot be empty.")

        self.command = list(command)
        self.config = config or UnixPTYConfig()

        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None

        self.process: Optional[subprocess.Popen] = None

        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        self.return_code: Optional[int] = None

        self.running = False
        self.closed = False

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._output = bytearray()
        self._output_lock = threading.RLock()

        self._callback: Optional[Callable[[str], None]] = None

        self._state_lock = threading.RLock()

    # ------------------------------------------------------------------
    # Platform
    # ------------------------------------------------------------------

    @staticmethod
    def supported() -> bool:
        """Return whether this backend can operate."""

        return os.name == "posix" and hasattr(pty, "openpty")

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(
        self,
        callback: Optional[Callable[[str], None]] = None,
    ) -> "UnixPTY":

        with self._state_lock:
            if self.running:
                raise UnixPTYError("PTY is already running.")

            if self.closed:
                raise UnixPTYClosedError("PTY has been closed.")

            if not self.supported():
                raise UnixPTYError(
                    "Unix PTY support is unavailable."
                )

            self._callback = callback

            self.master_fd, self.slave_fd = pty.openpty()

            self._configure_terminal_size(
                self.slave_fd,
                self.config.columns,
                self.config.rows,
            )

            preexec_fn = None

            if self.config.create_session:

                def create_session() -> None:
                    os.setsid()

                preexec_fn = create_session

            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdin=self.slave_fd,
                    stdout=self.slave_fd,
                    stderr=self.slave_fd,
                    cwd=self.config.cwd,
                    env=self.config.env,
                    preexec_fn=preexec_fn,
                    close_fds=True,
                )

            except Exception:
                self._close_fds()
                raise

            # Parent no longer needs the slave side.
            try:
                os.close(self.slave_fd)
            except OSError:
                pass

            self.slave_fd = None

            self.started_at = time.time()
            self.running = True

            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                name="Convexity-UnixPTY",
                daemon=True,
            )

            self._reader_thread.start()

        return self

    # ------------------------------------------------------------------
    # Terminal configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_terminal_size(
        fd: int,
        columns: int,
        rows: int,
    ) -> None:

        if columns <= 0 or rows <= 0:
            raise ValueError(
                "Terminal dimensions must be positive."
            )

        size = struct.pack(
            "HHHH",
            rows,
            columns,
            0,
            0,
        )

        fcntl.ioctl(
            fd,
            termios.TIOCSWINSZ,
            size,
        )

    # ------------------------------------------------------------------
    # Reader
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:

        if self.master_fd is None:
            return

        fd = self.master_fd

        while not self._stop_event.is_set():

            try:
                ready, _, _ = select.select(
                    [fd],
                    [],
                    [],
                    0.25,
                )

            except (OSError, ValueError):
                break

            if not ready:
                self._check_process()
                continue

            try:
                data = os.read(
                    fd,
                    self.config.read_size,
                )

            except OSError as exc:

                # EIO is normal when the slave side closes.
                if exc.errno in (
                    errno.EIO,
                    errno.EBADF,
                ):
                    break

                break

            if not data:
                break

            with self._output_lock:
                self._output.extend(data)

            text = data.decode(
                self.config.encoding,
                errors=self.config.errors,
            )

            if self._callback is not None:
                try:
                    self._callback(text)
                except Exception:
                    # Output callbacks must never kill the PTY reader.
                    pass

            self._check_process()

        self._check_process()

        with self._state_lock:
            self.running = False

            if self.finished_at is None:
                self.finished_at = time.time()

    # ------------------------------------------------------------------
    # Process state
    # ------------------------------------------------------------------

    def _check_process(self) -> None:

        if self.process is None:
            return

        code = self.process.poll()

        if code is not None:
            self.return_code = code

            with self._state_lock:
                self.running = False

                if self.finished_at is None:
                    self.finished_at = time.time()

    def poll(self) -> Optional[int]:
        """Return the child process return code."""

        self._check_process()

        return self.return_code

    def is_running(self) -> bool:
        """Return whether the child process is running."""

        self._check_process()

        return self.running

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def write(self, data: str | bytes) -> None:
        """Write data directly to the PTY master."""

        if self.master_fd is None or self.closed:
            raise UnixPTYClosedError(
                "PTY master is closed."
            )

        if isinstance(data, str):
            data = data.encode(
                self.config.encoding,
                errors=self.config.errors,
            )

        view = memoryview(data)

        while view:

            try:
                written = os.write(
                    self.master_fd,
                    view,
                )

                view = view[written:]

            except InterruptedError:
                continue

            except OSError as exc:
                raise UnixPTYError(
                    f"PTY write failed: {exc}"
                ) from exc

    def send_line(self, text: str) -> None:
        """Write text followed by a newline."""

        self.write(text + "\n")

    # ------------------------------------------------------------------
    # Control keys
    # ------------------------------------------------------------------

    def send_ctrl_c(self) -> None:
        """
        Send Ctrl+C to the foreground process group.

        This uses the Unix terminal's process-group semantics.
        """

        if self.master_fd is None:
            return

        self.write(b"\x03")

    def send_ctrl_d(self) -> None:
        """Send EOF."""

        if self.master_fd is None:
            return

        self.write(b"\x04")

    def send_ctrl_z(self) -> None:
        """Suspend the foreground process group."""

        if self.master_fd is None:
            return

        self.write(b"\x1a")

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(
        self,
        columns: int,
        rows: int,
    ) -> None:
        """Resize the PTY."""

        if self.master_fd is None:
            raise UnixPTYClosedError(
                "PTY master is not available."
            )

        self.config.columns = columns
        self.config.rows = rows

        self._configure_terminal_size(
            self.master_fd,
            columns,
            rows,
        )

    # ------------------------------------------------------------------
    # Process signals
    # ------------------------------------------------------------------

    def terminate(self) -> None:
        """Gracefully terminate the process group."""

        if self.process is None:
            return

        try:

            if self.config.create_session:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGTERM,
                )
            else:
                self.process.terminate()

        except ProcessLookupError:
            pass

    def kill(self) -> None:
        """Forcefully terminate the process group."""

        if self.process is None:
            return

        try:

            if self.config.create_session:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGKILL,
                )
            else:
                self.process.kill()

        except ProcessLookupError:
            pass

    # ------------------------------------------------------------------
    # Wait
    # ------------------------------------------------------------------

    def wait(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[int]:
        """Wait for the process."""

        if self.process is None:
            raise UnixPTYError(
                "PTY process has not started."
            )

        try:
            result = self.process.wait(
                timeout=timeout,
            )

        except subprocess.TimeoutExpired:
            raise UnixPTYError(
                "PTY process timed out."
            )

        self.return_code = result

        with self._state_lock:
            self.running = False

            if self.finished_at is None:
                self.finished_at = time.time()

        return result

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_output(self) -> str:
        """Return captured terminal output."""

        with self._output_lock:
            data = bytes(self._output)

        return data.decode(
            self.config.encoding,
            errors=self.config.errors,
        )

    def get_output_bytes(self) -> bytes:
        """Return raw captured terminal bytes."""

        with self._output_lock:
            return bytes(self._output)

    def clear_output(self) -> None:
        """Clear captured output."""

        with self._output_lock:
            self._output.clear()

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def duration(self) -> float:
        """Return elapsed session time."""

        if self.started_at is None:
            return 0.0

        end = self.finished_at or time.time()

        return end - self.started_at

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _close_fds(self) -> None:

        for attr in ("master_fd", "slave_fd"):

            fd = getattr(self, attr)

            if fd is not None:

                try:
                    os.close(fd)
                except OSError:
                    pass

                setattr(self, attr, None)

    def close(self) -> None:
        """Close the PTY and terminate the process if necessary."""

        if self.closed:
            return

        self._stop_event.set()

        if self.process is not None:

            if self.process.poll() is None:
                self.terminate()

        if self._reader_thread is not None:
            self._reader_thread.join(
                timeout=1.0,
            )

        self._close_fds()

        self.closed = True
        self.running = False

        if self.finished_at is None:
            self.finished_at = time.time()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "UnixPTY":
        return self.start()

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

def create_unix_pty(
    command: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    columns: int = 120,
    rows: int = 30,
    callback: Optional[Callable[[str], None]] = None,
) -> UnixPTY:

    config = UnixPTYConfig(
        cwd=cwd,
        env=env,
        columns=columns,
        rows=rows,
    )

    session = UnixPTY(
        command,
        config,
    )

    session.start(callback)

    return session


def is_unix_pty_supported() -> bool:
    """Return whether Unix PTY support is available."""

    return UnixPTY.supported()


__all__ = [
    "UnixPTYError",
    "UnixPTYClosedError",
    "UnixPTYConfig",
    "UnixPTY",
    "create_unix_pty",
    "is_unix_pty_supported",
]
"""
Convexity Android PTY Backend
Version: 0.8.3

Android/Linux pseudo-terminal backend.

Designed for:
- Android
- Linux-based environments
- Convexity Android application
- Native Convexity shell sessions

This module does NOT require Termux.

Android compatibility is provided through the Android/Linux
runtime itself.
"""

from __future__ import annotations

import os
import platform
import pty
import select
import signal
import struct
import subprocess
import termios
import threading
import time
import tty

from dataclasses import dataclass
from typing import Callable, Optional, Sequence


__version__ = "0.8.3"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AndroidPTYError(Exception):
    """Base Android PTY error."""


class AndroidPTYNotSupportedError(AndroidPTYError):
    """Raised when PTY support is unavailable."""


class AndroidPTYClosedError(AndroidPTYError):
    """Raised when the PTY is already closed."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AndroidPTYConfig:
    """Configuration for an Android PTY session."""

    cwd: Optional[str] = None

    env: Optional[dict[str, str]] = None

    columns: int = 120

    rows: int = 30

    encoding: str = "utf-8"

    errors: str = "replace"

    read_size: int = 4096

    raw_mode: bool = False


# ---------------------------------------------------------------------------
# Android PTY
# ---------------------------------------------------------------------------

class AndroidPTY:
    """
    Android/Linux PTY session.

    Architecture:

        Convexity
            |
            v
        PTY master
            |
            v
        PTY slave
            |
            v
        Convexity child process
    """

    def __init__(
        self,
        command: Sequence[str],
        config: Optional[AndroidPTYConfig] = None,
    ):
        if not command:
            raise ValueError(
                "Command cannot be empty."
            )

        self.command = list(command)

        self.config = (
            config or AndroidPTYConfig()
        )

        self.master_fd: Optional[int] = None

        self.child_pid: Optional[int] = None

        self.started_at: Optional[float] = None

        self.finished_at: Optional[float] = None

        self.return_code: Optional[int] = None

        self.running = False

        self.closed = False

        self._stop_event = threading.Event()

        self._reader_thread: Optional[
            threading.Thread
        ] = None

        self._output = bytearray()

        self._output_lock = threading.RLock()

        self._write_lock = threading.RLock()

        self._callback: Optional[
            Callable[[str], None]
        ] = None

        self._original_terminal_attributes = None

    # -----------------------------------------------------------------------
    # Support
    # -----------------------------------------------------------------------

    @staticmethod
    def supported() -> bool:
        """
        Check whether the current runtime provides POSIX PTY support.
        """

        if os.name != "posix":
            return False

        required = (
            "openpty",
            "fork",
        )

        return all(
            hasattr(pty, name)
            for name in required
        )

    # -----------------------------------------------------------------------
    # Start
    # -----------------------------------------------------------------------

    def start(
        self,
        callback: Optional[
            Callable[[str], None]
        ] = None,
    ) -> "AndroidPTY":

        if not self.supported():
            raise AndroidPTYNotSupportedError(
                "POSIX PTY support is unavailable."
            )

        if self.running:
            raise AndroidPTYError(
                "PTY is already running."
            )

        if self.closed:
            raise AndroidPTYClosedError(
                "PTY has already been closed."
            )

        self._callback = callback

        try:
            master_fd, slave_fd = pty.openpty()

        except OSError as exc:
            raise AndroidPTYError(
                f"Unable to create PTY: {exc}"
            ) from exc

        self.master_fd = master_fd

        self._configure_terminal(
            slave_fd
        )

        try:
            pid = os.fork()

        except OSError as exc:

            os.close(master_fd)
            os.close(slave_fd)

            self.master_fd = None

            raise AndroidPTYError(
                f"Unable to fork PTY process: {exc}"
            ) from exc

        if pid == 0:

            # Child process.
            try:
                self._child_process(
                    slave_fd
                )
            except BaseException:
                os._exit(127)

        # Parent process.
        self.child_pid = pid

        os.close(slave_fd)

        self.started_at = time.time()

        self.running = True

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="Convexity-AndroidPTY",
            daemon=True,
        )

        self._reader_thread.start()

        return self

    # -----------------------------------------------------------------------
    # Child
    # -----------------------------------------------------------------------

    def _child_process(
        self,
        slave_fd: int,
    ) -> None:

        # Become session leader.
        os.setsid()

        # Make the PTY the controlling terminal.
        try:
            import fcntl

            fcntl.ioctl(
                slave_fd,
                termios.TIOCSCTTY,
                0,
            )

        except Exception:
            pass

        # Connect standard streams.
        os.dup2(
            slave_fd,
            0,
        )

        os.dup2(
            slave_fd,
            1,
        )

        os.dup2(
            slave_fd,
            2,
        )

        if slave_fd > 2:
            os.close(slave_fd)

        # Set working directory.
        if self.config.cwd:

            try:
                os.chdir(
                    self.config.cwd
                )
            except OSError:
                pass

        # Environment.
        if self.config.env is not None:

            os.environ.clear()

            for key, value in self.config.env.items():
                os.environ[str(key)] = str(value)

        # Restore default signal behavior.
        signal.signal(
            signal.SIGINT,
            signal.SIG_DFL,
        )

        signal.signal(
            signal.SIGTERM,
            signal.SIG_DFL,
        )

        signal.signal(
            signal.SIGHUP,
            signal.SIG_DFL,
        )

        # Execute command.
        os.execvp(
            self.command[0],
            self.command,
        )

    # -----------------------------------------------------------------------
    # Terminal configuration
    # -----------------------------------------------------------------------

    def _configure_terminal(
        self,
        fd: int,
    ) -> None:

        try:

            self._set_terminal_size(
                fd,
                self.config.columns,
                self.config.rows,
            )

            if self.config.raw_mode:

                self._original_terminal_attributes = (
                    termios.tcgetattr(fd)
                )

                tty.setraw(fd)

        except Exception:
            # PTY creation itself remains usable even when
            # terminal configuration is unavailable.
            pass

    # -----------------------------------------------------------------------
    # Terminal size
    # -----------------------------------------------------------------------

    @staticmethod
    def _set_terminal_size(
        fd: int,
        columns: int,
        rows: int,
    ) -> None:

        import fcntl

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

    def resize(
        self,
        columns: int,
        rows: int,
    ) -> None:

        if self.master_fd is None:
            raise AndroidPTYError(
                "PTY master is unavailable."
            )

        if columns <= 0 or rows <= 0:
            raise ValueError(
                "Terminal dimensions must be positive."
            )

        self._set_terminal_size(
            self.master_fd,
            columns,
            rows,
        )

        self.config.columns = columns
        self.config.rows = rows

    # -----------------------------------------------------------------------
    # Reader
    # -----------------------------------------------------------------------

    def _reader_loop(self) -> None:

        while not self._stop_event.is_set():

            if self.master_fd is None:
                break

            try:

                readable, _, _ = select.select(
                    [self.master_fd],
                    [],
                    [],
                    0.25,
                )

            except (
                OSError,
                ValueError,
            ):
                break

            if not readable:
                self._update_process_state()
                continue

            try:

                data = os.read(
                    self.master_fd,
                    self.config.read_size,
                )

            except OSError:
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
                    pass

        self._update_process_state()

        self.running = False

        if self.finished_at is None:
            self.finished_at = time.time()

    # -----------------------------------------------------------------------
    # Process state
    # -----------------------------------------------------------------------

    def _update_process_state(self) -> None:

        if self.child_pid is None:
            return

        try:

            pid, status = os.waitpid(
                self.child_pid,
                os.WNOHANG,
            )

        except ChildProcessError:

            self.running = False
            return

        except OSError:
            return

        if pid == 0:
            return

        if os.WIFEXITED(status):

            self.return_code = (
                os.WEXITSTATUS(status)
            )

        elif os.WIFSIGNALED(status):

            self.return_code = (
                -os.WTERMSIG(status)
            )

        self.running = False

        if self.finished_at is None:
            self.finished_at = time.time()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def write(
        self,
        data: str | bytes,
    ) -> None:

        if self.closed:
            raise AndroidPTYClosedError(
                "PTY is closed."
            )

        if self.master_fd is None:
            raise AndroidPTYError(
                "PTY master is unavailable."
            )

        if isinstance(data, str):

            data = data.encode(
                self.config.encoding,
                errors=self.config.errors,
            )

        with self._write_lock:

            try:
                os.write(
                    self.master_fd,
                    data,
                )

            except OSError as exc:
                raise AndroidPTYError(
                    f"PTY write failed: {exc}"
                ) from exc

    def send_line(
        self,
        text: str,
    ) -> None:

        self.write(
            text + "\r"
        )

    # -----------------------------------------------------------------------
    # Terminal control
    # -----------------------------------------------------------------------

    def send_ctrl_c(self) -> None:
        """Send Ctrl+C."""

        self.write(b"\x03")

    def send_ctrl_d(self) -> None:
        """Send EOF."""

        self.write(b"\x04")

    def send_ctrl_z(self) -> None:
        """Send Ctrl+Z."""

        self.write(b"\x1a")

    # -----------------------------------------------------------------------
    # Process control
    # -----------------------------------------------------------------------

    def terminate(self) -> None:

        if self.child_pid is None:
            return

        try:

            os.kill(
                self.child_pid,
                signal.SIGTERM,
            )

        except ProcessLookupError:
            pass

        except OSError:
            pass

    def kill(self) -> None:

        if self.child_pid is None:
            return

        try:

            os.kill(
                self.child_pid,
                signal.SIGKILL,
            )

        except ProcessLookupError:
            pass

        except OSError:
            pass

    def signal(
        self,
        sig: int,
    ) -> None:

        if self.child_pid is None:
            raise AndroidPTYError(
                "No child process."
            )

        os.kill(
            self.child_pid,
            sig,
        )

    # -----------------------------------------------------------------------
    # Waiting
    # -----------------------------------------------------------------------

    def wait(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[int]:

        if self.child_pid is None:
            return self.return_code

        start = time.monotonic()

        while self.running:

            self._update_process_state()

            if not self.running:
                break

            if timeout is not None:

                if (
                    time.monotonic() - start
                    >= timeout
                ):
                    return None

            time.sleep(0.02)

        return self.return_code

    def poll(self) -> Optional[int]:

        self._update_process_state()

        return self.return_code

    def is_running(self) -> bool:

        self._update_process_state()

        return self.running

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------

    def get_output(self) -> str:

        with self._output_lock:
            data = bytes(self._output)

        return data.decode(
            self.config.encoding,
            errors=self.config.errors,
        )

    def get_output_bytes(self) -> bytes:

        with self._output_lock:
            return bytes(self._output)

    def clear_output(self) -> None:

        with self._output_lock:
            self._output.clear()

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def close(self) -> None:

        if self.closed:
            return

        self._stop_event.set()

        if self.running:
            self.terminate()

        if self._reader_thread is not None:

            self._reader_thread.join(
                timeout=1.0
            )

        if self.master_fd is not None:

            try:
                os.close(
                    self.master_fd
                )
            except OSError:
                pass

            self.master_fd = None

        self.running = False

        self.closed = True

        if self.finished_at is None:
            self.finished_at = time.time()

    # -----------------------------------------------------------------------
    # Context manager
    # -----------------------------------------------------------------------

    def __enter__(self) -> "AndroidPTY":
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

def create_android_pty(
    command: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    columns: int = 120,
    rows: int = 30,
    callback: Optional[
        Callable[[str], None]
    ] = None,
) -> AndroidPTY:

    config = AndroidPTYConfig(
        cwd=cwd,
        env=env,
        columns=columns,
        rows=rows,
    )

    session = AndroidPTY(
        command,
        config,
    )

    session.start(callback)

    return session


def is_android_pty_supported() -> bool:
    """Return whether Android/Linux PTY support is available."""

    return AndroidPTY.supported()


__all__ = [
    "AndroidPTYError",
    "AndroidPTYNotSupportedError",
    "AndroidPTYClosedError",
    "AndroidPTYConfig",
    "AndroidPTY",
    "create_android_pty",
    "is_android_pty_supported",
]
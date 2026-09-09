"""
Convexity Windows ConPTY Backend
Version: 0.8.2

Direct Windows pseudo-console backend.

Convexity does not depend on:
- PowerShell
- CMD
- Git Bash
- Termux

This module uses the Windows Pseudo Console (ConPTY) API.

Requires:
- Windows 10 version 1809 or newer
- Windows 11
- Python running on Windows
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Optional, Sequence


__version__ = "0.8.2"


# ---------------------------------------------------------------------------
# Windows detection
# ---------------------------------------------------------------------------

IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WindowsPTYError(Exception):
    """Base Windows PTY error."""


class WindowsPTYNotSupportedError(WindowsPTYError):
    """Raised when ConPTY is unavailable."""


class WindowsPTYClosedError(WindowsPTYError):
    """Raised when the PTY has already been closed."""


# ---------------------------------------------------------------------------
# Windows API
# ---------------------------------------------------------------------------

if IS_WINDOWS:

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # HANDLE
    HANDLE = wintypes.HANDLE

    # HRESULT
    HRESULT = ctypes.c_long

    # COORD
    class COORD(ctypes.Structure):
        _fields_ = [
            ("X", wintypes.SHORT),
            ("Y", wintypes.SHORT),
        ]

    # SECURITY_ATTRIBUTES
    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        ]

    # PROC_THREAD_ATTRIBUTE_LIST is opaque.
    class PROC_THREAD_ATTRIBUTE_LIST(ctypes.Structure):
        _fields_ = [
            ("dummy", wintypes.BYTE),
        ]

    # STARTUPINFOEX
    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", subprocess.STARTUPINFO),
            ("lpAttributeList", ctypes.c_void_p),
        ]

    # Windows constants
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000

    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016

    HANDLE_FLAG_INHERIT = 0x00000001

    CREATE_UNICODE_ENVIRONMENT = 0x00000400

    INFINITE = 0xFFFFFFFF

    ERROR_INSUFFICIENT_BUFFER = 122

    # -----------------------------------------------------------------------
    # API declarations
    # -----------------------------------------------------------------------

    kernel32.CreatePipe.argtypes = [
        ctypes.POINTER(HANDLE),
        ctypes.POINTER(HANDLE),
        ctypes.POINTER(SECURITY_ATTRIBUTES),
        wintypes.DWORD,
    ]

    kernel32.CreatePipe.restype = wintypes.BOOL

    kernel32.SetHandleInformation.argtypes = [
        HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
    ]

    kernel32.SetHandleInformation.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [HANDLE]

    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.CreatePseudoConsole.argtypes = [
        COORD,
        HANDLE,
        HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(HANDLE),
    ]

    kernel32.CreatePseudoConsole.restype = HRESULT

    kernel32.ResizePseudoConsole.argtypes = [
        HANDLE,
        COORD,
    ]

    kernel32.ResizePseudoConsole.restype = HRESULT

    kernel32.ClosePseudoConsole.argtypes = [
        HANDLE,
    ]

    kernel32.ClosePseudoConsole.restype = None

    kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]

    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL

    kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL

    kernel32.DeleteProcThreadAttributeList.argtypes = [
        ctypes.c_void_p,
    ]

    kernel32.DeleteProcThreadAttributeList.restype = None

    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOEXW),
        ctypes.c_void_p,
    ]

    kernel32.CreateProcessW.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WindowsPTYConfig:
    """Configuration for a Windows ConPTY session."""

    cwd: Optional[str] = None

    env: Optional[dict[str, str]] = None

    columns: int = 120
    rows: int = 30

    encoding: str = "utf-8"

    errors: str = "replace"

    read_size: int = 4096


# ---------------------------------------------------------------------------
# Windows PTY
# ---------------------------------------------------------------------------

class WindowsPTY:
    """
    Windows ConPTY session.

    Architecture:

        Convexity
            |
            +---- input pipe ----+
            |                    |
            |                 ConPTY
            |                    |
            +--- output pipe ----+
                     |
                  Process
    """

    def __init__(
        self,
        command: Sequence[str],
        config: Optional[WindowsPTYConfig] = None,
    ):
        if not command:
            raise ValueError(
                "Command cannot be empty."
            )

        self.command = list(command)

        self.config = (
            config or WindowsPTYConfig()
        )

        self.hpc: Optional[HANDLE] = None

        self.input_read: Optional[HANDLE] = None
        self.input_write: Optional[HANDLE] = None

        self.output_read: Optional[HANDLE] = None
        self.output_write: Optional[HANDLE] = None

        self.process_handle: Optional[HANDLE] = None
        self.thread_handle: Optional[HANDLE] = None

        self.process_id: Optional[int] = None

        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        self.return_code: Optional[int] = None

        self.running = False
        self.closed = False

        self._output = bytearray()
        self._output_lock = threading.RLock()

        self._reader_thread: Optional[
            threading.Thread
        ] = None

        self._stop_event = threading.Event()

        self._callback: Optional[
            Callable[[str], None]
        ] = None

    # -----------------------------------------------------------------------
    # Support
    # -----------------------------------------------------------------------

    @staticmethod
    def supported() -> bool:
        """Return whether this backend is available."""

        if not IS_WINDOWS:
            return False

        version = platform.version()

        # ConPTY was introduced in Windows 10 1809.
        #
        # We additionally verify the API exists.
        try:
            getattr(
                kernel32,
                "CreatePseudoConsole",
            )
            return True
        except AttributeError:
            return False

    # -----------------------------------------------------------------------
    # Start
    # -----------------------------------------------------------------------

    def start(
        self,
        callback: Optional[
            Callable[[str], None]
        ] = None,
    ) -> "WindowsPTY":

        if not self.supported():
            raise WindowsPTYNotSupportedError(
                "Windows ConPTY is not available."
            )

        if self.running:
            raise WindowsPTYError(
                "PTY is already running."
            )

        if self.closed:
            raise WindowsPTYClosedError(
                "PTY has been closed."
            )

        self._callback = callback

        self._create_pipes()

        self._create_pseudoconsole()

        try:
            self._create_process()
        except Exception:
            self.close()
            raise

        self.started_at = time.time()
        self.running = True

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="Convexity-WindowsPTY",
            daemon=True,
        )

        self._reader_thread.start()

        return self

    # -----------------------------------------------------------------------
    # Pipes
    # -----------------------------------------------------------------------

    def _create_pipes(self) -> None:

        security = SECURITY_ATTRIBUTES()

        security.nLength = ctypes.sizeof(
            SECURITY_ATTRIBUTES
        )

        security.lpSecurityDescriptor = None

        security.bInheritHandle = True

        # Input pipe.
        input_read = HANDLE()
        input_write = HANDLE()

        if not kernel32.CreatePipe(
            ctypes.byref(input_read),
            ctypes.byref(input_write),
            ctypes.byref(security),
            0,
        ):
            raise WindowsPTYError(
                "Failed to create ConPTY input pipe."
            )

        # Output pipe.
        output_read = HANDLE()
        output_write = HANDLE()

        if not kernel32.CreatePipe(
            ctypes.byref(output_read),
            ctypes.byref(output_write),
            ctypes.byref(security),
            0,
        ):
            kernel32.CloseHandle(input_read)
            kernel32.CloseHandle(input_write)

            raise WindowsPTYError(
                "Failed to create ConPTY output pipe."
            )

        # Parent-owned handles must not be inherited.
        kernel32.SetHandleInformation(
            input_write,
            HANDLE_FLAG_INHERIT,
            0,
        )

        kernel32.SetHandleInformation(
            output_read,
            HANDLE_FLAG_INHERIT,
            0,
        )

        self.input_read = input_read
        self.input_write = input_write

        self.output_read = output_read
        self.output_write = output_write

    # -----------------------------------------------------------------------
    # ConPTY
    # -----------------------------------------------------------------------

    def _create_pseudoconsole(self) -> None:

        if self.input_read is None:
            raise WindowsPTYError(
                "Input pipe is unavailable."
            )

        if self.output_write is None:
            raise WindowsPTYError(
                "Output pipe is unavailable."
            )

        size = COORD(
            self.config.columns,
            self.config.rows,
        )

        hpc = HANDLE()

        result = kernel32.CreatePseudoConsole(
            size,
            self.input_read,
            self.output_write,
            0,
            ctypes.byref(hpc),
        )

        if result != 0:
            raise WindowsPTYError(
                f"CreatePseudoConsole failed: HRESULT {result}"
            )

        self.hpc = hpc

    # -----------------------------------------------------------------------
    # Process creation
    # -----------------------------------------------------------------------

    def _build_command_line(self) -> str:

        # subprocess.list2cmdline implements Windows command
        # line quoting rules.
        return subprocess.list2cmdline(
            self.command
        )

    def _create_process(self) -> None:

        if self.hpc is None:
            raise WindowsPTYError(
                "Pseudo console has not been created."
            )

        # First determine required attribute-list size.
        size = ctypes.c_size_t(0)

        kernel32.InitializeProcThreadAttributeList(
            None,
            1,
            0,
            ctypes.byref(size),
        )

        buffer = ctypes.create_string_buffer(
            size.value
        )

        attribute_list = ctypes.cast(
            buffer,
            ctypes.c_void_p,
        )

        if not kernel32.InitializeProcThreadAttributeList(
            attribute_list,
            1,
            0,
            ctypes.byref(size),
        ):
            raise WindowsPTYError(
                "Failed to initialize process attribute list."
            )

        try:

            hpc_value = ctypes.c_void_p(
                self.hpc.value
            )

            if not kernel32.UpdateProcThreadAttribute(
                attribute_list,
                0,
                PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                ctypes.byref(hpc_value),
                ctypes.sizeof(hpc_value),
                None,
                None,
            ):
                raise WindowsPTYError(
                    "Failed to attach ConPTY to process."
                )

            startup = STARTUPINFOEXW()

            startup.StartupInfo.cb = ctypes.sizeof(
                STARTUPINFOEXW
            )

            startup.lpAttributeList = attribute_list

            command_line = self._build_command_line()

            command_buffer = ctypes.create_unicode_buffer(
                command_line
            )

            environment_block = None

            if self.config.env is not None:

                environment_block = self._build_environment_block()

            process_info = ctypes.create_string_buffer(
                ctypes.sizeof(
                    wintypes.HANDLE
                ) * 2 + 8
            )

            # Use the standard subprocess STARTUPINFO layout
            # through a secondary fallback when direct creation
            # is unavailable from the current Python ABI.
            #
            # This backend intentionally exposes the native
            # ConPTY abstraction; production packaging should
            # validate the Windows ABI during installation.

            creation_flags = (
                EXTENDED_STARTUPINFO_PRESENT
                | CREATE_UNICODE_ENVIRONMENT
            )

            success = kernel32.CreateProcessW(
                None,
                command_buffer,
                None,
                None,
                False,
                creation_flags,
                environment_block,
                self.config.cwd,
                ctypes.byref(startup),
                ctypes.byref(process_info),
            )

            if not success:
                error = ctypes.get_last_error()

                raise WindowsPTYError(
                    f"CreateProcessW failed: Windows error {error}"
                )

            # The raw process-info structure contains handles.
            handle_size = ctypes.sizeof(HANDLE)

            self.process_handle = HANDLE.from_buffer_copy(
                process_info.raw[
                    :handle_size
                ]
            )

            self.thread_handle = HANDLE.from_buffer_copy(
                process_info.raw[
                    handle_size:handle_size * 2
                ]
            )

        finally:

            kernel32.DeleteProcThreadAttributeList(
                attribute_list
            )

    # -----------------------------------------------------------------------
    # Environment
    # -----------------------------------------------------------------------

    def _build_environment_block(self):

        if self.config.env is None:
            return None

        entries = []

        for key, value in self.config.env.items():
            entries.append(
                f"{key}={value}"
            )

        entries.sort(
            key=lambda value: value.lower()
        )

        block = "\0".join(entries) + "\0\0"

        return ctypes.create_unicode_buffer(
            block
        )

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------

    def _reader_loop(self) -> None:
        """
        Read output from the ConPTY output pipe.

        A production implementation can replace this reader
        with overlapped I/O for higher-performance workloads.
        """

        # The low-level synchronous ReadFile implementation
        # is intentionally isolated here so it can later be
        # replaced without changing WindowsPTY's public API.

        while not self._stop_event.is_set():

            if self.output_read is None:
                break

            try:
                data = os.read(
                    self._handle_to_fd(
                        self.output_read
                    ),
                    self.config.read_size,
                )

            except (OSError, ValueError):
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

        self.running = False

        if self.finished_at is None:
            self.finished_at = time.time()

    # -----------------------------------------------------------------------
    # Handle conversion
    # -----------------------------------------------------------------------

    @staticmethod
    def _handle_to_fd(
        handle: HANDLE,
    ) -> int:
        """
        Convert a Windows pipe HANDLE into a Python file descriptor.

        Python's os.read requires a CRT descriptor.
        """

        import msvcrt

        return msvcrt.open_osfhandle(
            handle.value,
            os.O_RDONLY,
        )

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def write(
        self,
        data: str | bytes,
    ) -> None:

        if self.closed:
            raise WindowsPTYClosedError(
                "PTY is closed."
            )

        if self.input_write is None:
            raise WindowsPTYError(
                "PTY input pipe is unavailable."
            )

        if isinstance(data, str):
            data = data.encode(
                self.config.encoding,
                errors=self.config.errors,
            )

        fd = self._handle_to_fd(
            self.input_write
        )

        try:
            os.write(fd, data)
        except OSError as exc:
            raise WindowsPTYError(
                f"PTY write failed: {exc}"
            ) from exc

    def send_line(self, text: str) -> None:
        """Send text followed by Enter."""

        self.write(text + "\r\n")

    # -----------------------------------------------------------------------
    # Resize
    # -----------------------------------------------------------------------

    def resize(
        self,
        columns: int,
        rows: int,
    ) -> None:

        if self.hpc is None:
            raise WindowsPTYError(
                "Pseudo console is not available."
            )

        if columns <= 0 or rows <= 0:
            raise ValueError(
                "Terminal dimensions must be positive."
            )

        size = COORD(
            columns,
            rows,
        )

        result = kernel32.ResizePseudoConsole(
            self.hpc,
            size,
        )

     
"""
Convexity PTY Platform Adapter
Version: 0.8.4

Provides one unified interface for Convexity PTY sessions.

Backend selection:
    Windows -> Windows ConPTY
    Android -> Android/Linux PTY
    Linux/macOS/Unix -> Unix PTY

The rest of Convexity should use this module rather than
importing platform-specific PTY implementations directly.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Any


__version__ = "0.8.4"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PTYPlatformError(Exception):
    """Base platform adapter error."""


class PTYPlatformNotSupportedError(PTYPlatformError):
    """Raised when no supported PTY backend exists."""


# ---------------------------------------------------------------------------
# Platform information
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PTYPlatformInfo:
    """Information about the detected execution platform."""

    name: str
    system: str
    release: str
    machine: str
    backend: str
    supported: bool
    reason: str = ""


def is_android() -> bool:
    """
    Detect Android.

    Android normally reports Linux through Python's platform module,
    so additional Android-specific environment/system indicators
    are checked.
    """

    if os.environ.get("ANDROID_ROOT"):
        return True

    if os.environ.get("ANDROID_DATA"):
        return True

    if os.path.exists("/system/bin"):
        return True

    if os.path.exists("/system/build.prop"):
        return True

    return False


def detect_platform() -> str:
    """
    Return the normalized Convexity platform name.

    Possible values:
        windows
        android
        unix
        unknown
    """

    system = platform.system().lower()

    if system == "windows":
        return "windows"

    if is_android():
        return "android"

    if system in {
        "linux",
        "darwin",
        "freebsd",
        "openbsd",
        "netbsd",
        "dragonfly",
        "aix",
        "sunos",
    }:
        return "unix"

    return "unknown"


def get_platform_info() -> PTYPlatformInfo:
    """Return detailed PTY platform information."""

    detected = detect_platform()

    system = platform.system()
    release = platform.release()
    machine = platform.machine()

    if detected == "windows":

        try:
            from .pty_windows import (
                is_windows_pty_supported,
            )

            supported = (
                is_windows_pty_supported()
            )

            reason = (
                ""
                if supported
                else "Windows ConPTY is unavailable."
            )

        except Exception as exc:

            supported = False

            reason = str(exc)

        return PTYPlatformInfo(
            name="Windows",
            system=system,
            release=release,
            machine=machine,
            backend="windows",
            supported=supported,
            reason=reason,
        )

    if detected == "android":

        try:
            from .pty_android import (
                is_android_pty_supported,
            )

            supported = (
                is_android_pty_supported()
            )

            reason = (
                ""
                if supported
                else "Android/Linux PTY support is unavailable."
            )

        except Exception as exc:

            supported = False

            reason = str(exc)

        return PTYPlatformInfo(
            name="Android",
            system=system,
            release=release,
            machine=machine,
            backend="android",
            supported=supported,
            reason=reason,
        )

    if detected == "unix":

        try:
            from .pty_unix import (
                is_unix_pty_supported,
            )

            supported = (
                is_unix_pty_supported()
            )

            reason = (
                ""
                if supported
                else "Unix PTY support is unavailable."
            )

        except Exception as exc:

            supported = False

            reason = str(exc)

        return PTYPlatformInfo(
            name="Unix",
            system=system,
            release=release,
            machine=machine,
            backend="unix",
            supported=supported,
            reason=reason,
        )

    return PTYPlatformInfo(
        name="Unknown",
        system=system,
        release=release,
        machine=machine,
        backend="none",
        supported=False,
        reason=(
            f"Unsupported platform: {system}"
        ),
    )


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def get_backend_class():
    """
    Return the PTY class appropriate for the current platform.
    """

    platform_name = detect_platform()

    if platform_name == "windows":

        from .pty_windows import WindowsPTY

        return WindowsPTY

    if platform_name == "android":

        from .pty_android import AndroidPTY

        return AndroidPTY

    if platform_name == "unix":

        from .pty_unix import UnixPTY

        return UnixPTY

    raise PTYPlatformNotSupportedError(
        "No PTY backend is available for this platform."
    )


def get_backend_config_class():
    """Return the configuration class for the active backend."""

    platform_name = detect_platform()

    if platform_name == "windows":

        from .pty_windows import (
            WindowsPTYConfig,
        )

        return WindowsPTYConfig

    if platform_name == "android":

        from .pty_android import (
            AndroidPTYConfig,
        )

        return AndroidPTYConfig

    if platform_name == "unix":

        from .pty_unix import (
            UnixPTYConfig,
        )

        return UnixPTYConfig

    raise PTYPlatformNotSupportedError(
        "No PTY configuration backend is available."
    )


# ---------------------------------------------------------------------------
# Unified PTY creation
# ---------------------------------------------------------------------------

def create_platform_pty(
    command: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    columns: int = 120,
    rows: int = 30,
    callback: Optional[
        Callable[[str], None]
    ] = None,
    **kwargs: Any,
):
    """
    Create a PTY using the correct platform backend.

    The caller does not need to know whether Convexity is
    running on Windows, Android, Linux, or another Unix system.
    """

    if not command:
        raise ValueError(
            "Command cannot be empty."
        )

    platform_name = detect_platform()

    if platform_name == "windows":

        from .pty_windows import (
            create_windows_pty,
        )

        return create_windows_pty(
            command,
            cwd=cwd,
            env=env,
            columns=columns,
            rows=rows,
            callback=callback,
        )

    if platform_name == "android":

        from .pty_android import (
            create_android_pty,
        )

        return create_android_pty(
            command,
            cwd=cwd,
            env=env,
            columns=columns,
            rows=rows,
            callback=callback,
        )

    if platform_name == "unix":

        from .pty_unix import (
            create_unix_pty,
        )

        return create_unix_pty(
            command,
            cwd=cwd,
            env=env,
            columns=columns,
            rows=rows,
            callback=callback,
        )

    raise PTYPlatformNotSupportedError(
        "Convexity does not currently have a PTY backend "
        "for this operating system."
    )


# ---------------------------------------------------------------------------
# Capability checks
# ---------------------------------------------------------------------------

def is_pty_supported() -> bool:
    """Return whether the current platform has a usable PTY backend."""

    try:
        return get_platform_info().supported
    except Exception:
        return False


def get_pty_backend_name() -> str:
    """Return the active backend name."""

    return get_platform_info().backend


def get_pty_capabilities() -> dict[str, Any]:
    """
    Return capabilities exposed by the active platform.

    These values allow higher-level Convexity components to
    adapt without hardcoding operating-system checks.
    """

    info = get_platform_info()

    capabilities = {
        "supported": info.supported,
        "backend": info.backend,
        "interactive_input": info.supported,
        "interactive_output": info.supported,
        "resize": info.supported,
        "process_control": info.supported,
        "ctrl_c": info.supported,
        "ctrl_z": False,
        "process_groups": False,
        "full_screen_terminal": info.supported,
    }

    if info.backend in {
        "unix",
        "android",
    }:
        capabilities.update(
            {
                "ctrl_z": True,
                "process_groups": True,
            }
        )

    if info.backend == "windows":
        capabilities.update(
            {
                "ctrl_z": False,
                "process_groups": True,
            }
        )

    return capabilities


# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

create_pty = create_platform_pty


__all__ = [
    "PTYPlatformError",
    "PTYPlatformNotSupportedError",
    "PTYPlatformInfo",
    "is_android",
    "detect_platform",
    "get_platform_info",
    "get_backend_class",
    "get_backend_config_class",
    "create_platform_pty",
    "create_pty",
    "is_pty_supported",
    "get_pty_backend_name",
    "get_pty_capabilities",
]
"""
Convexity Package Manager
Version: 0.9.1

Native package-management abstraction for Convexity.

Convexity does not depend on Termux, PowerShell, or CMD.
However, it can use package managers available on the
underlying operating system.

Supported package-manager adapters:
- pip
- pip3
- npm
- pnpm
- yarn
- apt
- apk
- pacman
- winget
- choco

Package managers are detected dynamically.

All installation and removal operations should pass
through Convexity's security and permission layer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from .config import config
from .security import (
    SecurityError,
    check_command,
)


__version__ = "0.9.1"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PackageManagerError(Exception):
    """Base package manager error."""


class PackageManagerNotFoundError(PackageManagerError):
    """Raised when a package manager is unavailable."""


class PackageOperationError(PackageManagerError):
    """Raised when a package operation fails."""


class PackagePermissionError(PackageManagerError):
    """Raised when a package operation is denied."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PackageManagerInfo:
    """Information about a detected package manager."""

    name: str

    executable: str

    ecosystem: str

    available: bool

    version: Optional[str] = None

    path: Optional[str] = None

    description: str = ""


@dataclass
class PackageResult:
    """Result of a package operation."""

    success: bool

    operation: str

    package: Optional[str] = None

    manager: Optional[str] = None

    return_code: Optional[int] = None

    stdout: str = ""

    stderr: str = ""

    message: str = ""

    duration: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class InstalledPackage:
    """A package recorded in Convexity's package registry."""

    name: str

    manager: str

    ecosystem: str

    version: Optional[str] = None

    installed_at: float = field(
        default_factory=time.time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Package manager definitions
# ---------------------------------------------------------------------------

PACKAGE_MANAGERS: dict[str, dict[str, Any]] = {
    "pip": {
        "executable": "pip",
        "ecosystem": "python",
        "description": "Python package installer",
    },
    "pip3": {
        "executable": "pip3",
        "ecosystem": "python",
        "description": "Python 3 package installer",
    },
    "python-pip": {
        "executable": sys.executable,
        "ecosystem": "python",
        "description": "Python package installer through the active interpreter",
        "special": "python-pip",
    },
    "npm": {
        "executable": "npm",
        "ecosystem": "node",
        "description": "Node.js package manager",
    },
    "pnpm": {
        "executable": "pnpm",
        "ecosystem": "node",
        "description": "Fast Node.js package manager",
    },
    "yarn": {
        "executable": "yarn",
        "ecosystem": "node",
        "description": "Node.js package manager",
    },
    "apt": {
        "executable": "apt",
        "ecosystem": "system",
        "description": "Debian and Ubuntu package manager",
    },
    "apt-get": {
        "executable": "apt-get",
        "ecosystem": "system",
        "description": "Debian and Ubuntu package manager",
    },
    "apk": {
        "executable": "apk",
        "ecosystem": "system",
        "description": "Alpine and Android-compatible package manager",
    },
    "pacman": {
        "executable": "pacman",
        "ecosystem": "system",
        "description": "Arch Linux package manager",
    },
    "winget": {
        "executable": "winget",
        "ecosystem": "system",
        "description": "Windows package manager",
    },
    "choco": {
        "executable": "choco",
        "ecosystem": "system",
        "description": "Chocolatey package manager",
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PackageRegistry:
    """
    Local registry of packages installed through Convexity.

    This registry is informational. The actual package manager
    remains the authority for package state.
    """

    def __init__(
        self,
        path: Optional[str] = None,
    ):

        if path is None:

            path = os.path.join(
                os.path.expanduser("~"),
                ".convexity",
                "packages.json",
            )

        self.path = Path(path)

        self._packages: dict[
            str,
            InstalledPackage,
        ] = {}

        self._load()

    # -----------------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------------

    def _load(self) -> None:

        if not self.path.exists():
            return

        try:

            raw = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return

        if not isinstance(raw, list):
            return

        for item in raw:

            if not isinstance(item, dict):
                continue

            try:

                package = InstalledPackage(
                    name=str(
                        item["name"]
                    ),
                    manager=str(
                        item["manager"]
                    ),
                    ecosystem=str(
                        item["ecosystem"]
                    ),
                    version=item.get(
                        "version"
                    ),
                    installed_at=float(
                        item.get(
                            "installed_at",
                            time.time(),
                        )
                    ),
                    metadata=dict(
                        item.get(
                            "metadata",
                            {},
                        )
                    ),
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            self._packages[
                self._key(
                    package.name,
                    package.manager,
                )
            ] = package

    def _save(self) -> None:

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = [
            asdict(package)
            for package in self._packages.values()
        ]

        self.path.write_text(
            json.dumps(
                data,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _key(
        name: str,
        manager: str,
    ) -> str:

        return (
            f"{manager.lower()}::"
            f"{name.lower()}"
        )

    # -----------------------------------------------------------------------
    # Registry operations
    # -----------------------------------------------------------------------

    def add(
        self,
        package: InstalledPackage,
    ) -> None:

        self._packages[
            self._key(
                package.name,
                package.manager,
            )
        ] = package

        self._save()

    def remove(
        self,
        name: str,
        manager: str,
    ) -> bool:

        key = self._key(
            name,
            manager,
        )

        if key not in self._packages:
            return False

        del self._packages[key]

        self._save()

        return True

    def get(
        self,
        name: str,
        manager: str,
    ) -> Optional[InstalledPackage]:

        return self._packages.get(
            self._key(
                name,
                manager,
            )
        )

    def list(
        self,
        manager: Optional[str] = None,
    ) -> list[InstalledPackage]:

        packages = list(
            self._packages.values()
        )

        if manager is not None:

            packages = [
                package
                for package in packages
                if package.manager.lower()
                == manager.lower()
            ]

        return sorted(
            packages,
            key=lambda package: (
                package.manager.lower(),
                package.name.lower(),
            ),
        )


# ---------------------------------------------------------------------------
# Package manager
# ---------------------------------------------------------------------------

class ConvexityPackageManager:

    def __init__(
        self,
        registry: Optional[PackageRegistry] = None,
    ):

        self.registry = (
            registry or PackageRegistry()
        )

    # -----------------------------------------------------------------------
    # Detection
    # -----------------------------------------------------------------------

    def detect(
        self,
    ) -> list[PackageManagerInfo]:

        result = []

        for name, definition in PACKAGE_MANAGERS.items():

            executable = definition[
                "executable"
            ]

            special = definition.get(
                "special"
            )

            if special == "python-pip":

                available = True

                path = sys.executable

                version = self._get_version(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "--version",
                    ]
                )

            else:

                path = shutil.which(
                    executable
                )

                available = path is not None

                version = (
                    self._get_version(
                        [
                            executable,
                            "--version",
                        ]
                    )
                    if available
                    else None
                )

            result.append(
                PackageManagerInfo(
                    name=name,
                    executable=executable,
                    ecosystem=definition[
                        "ecosystem"
                    ],
                    available=available,
                    version=version,
                    path=path,
                    description=definition[
                        "description"
                    ],
                )
            )

        return result

    def available_managers(
        self,
    ) -> list[PackageManagerInfo]:

        return [
            manager
            for manager in self.detect()
            if manager.available
        ]

    def get_manager(
        self,
        name: str,
    ) -> PackageManagerInfo:

        normalized = name.lower().strip()

        for manager in self.detect():

            if manager.name.lower() == normalized:

                if not manager.available:

                    raise PackageManagerNotFoundError(
                        f"Package manager is unavailable: {name}"
                    )

                return manager

        raise PackageManagerNotFoundError(
            f"Unknown package manager: {name}"
        )

    # -----------------------------------------------------------------------
    # Version
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_version(
        command: Sequence[str],
    ) -> Optional[str]:

        try:

            result = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )

        except (
            OSError,
            subprocess.SubprocessError,
        ):

            return None

        output = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        if not output:
            return None

        return output.splitlines()[0]

    # -----------------------------------------------------------------------
    # Command construction
    # -----------------------------------------------------------------------

    def _build_command(
        self,
        manager: str,
        operation: str,
        package: Optional[str] = None,
        extra_args: Optional[
            Sequence[str]
        ] = None,
    ) -> list[str]:

        manager_info = self.get_manager(
            manager
        )

        special = PACKAGE_MANAGERS[
            manager_info.name
        ].get("special")

        if special == "python-pip":

            command = [
                sys.executable,
                "-m",
                "pip",
            ]

        else:

            command = [
                manager_info.executable
            ]

        if operation == "install":

            if manager_info.name in {
                "pip",
                "pip3",
                "python-pip",
            }:

                command.append("install")

            elif manager_info.name in {
                "npm",
                "pnpm",
                "yarn",
            }:

                command.append("install")

            elif manager_info.name in {
                "apt",
                "apt-get",
            }:

                command.extend(
                    [
                        "install",
                        "-y",
                    ]
                )

            elif manager_info.name == "apk":

                command.extend(
                    [
                        "add",
                    ]
                )

            elif manager_info.name == "pacman":

                command.extend(
                    [
                        "-S",
                        "--noconfirm",
                    ]
                )

            elif manager_info.name == "winget":

                command.extend(
                    [
                        "install",
                        "--accept-source-agreements",
                        "--accept-package-agreements",
                    ]
                )

            elif manager_info.name == "choco":

                command.extend(
                    [
                        "install",
                        "-y",
                    ]
                )

        elif operation == "remove":

            if manager_info.name in {
                "pip",
                "pip3",
                "python-pip",
            }:

                command.append("uninstall")
                command.append("-y")

            elif manager_info.name in {
                "npm",
                "pnpm",
                "yarn",
            }:

                command.append("uninstall")

            elif manager_info.name in {
                "apt",
                "apt-get",
            }:

                command.extend(
                    [
                        "remove",
                        "-y",
                    ]
                )

            elif manager_info.name == "apk":

                command.append("del")

            elif manager_info.name == "pacman":

                command.extend(
                    [
                        "-R",
                        "--noconfirm",
                    ]
                )

            elif manager_info.name == "winget":

                command.append("uninstall")

            elif manager_info.name == "choco":

                command.extend(
                    [
                        "uninstall",
                        "-y",
                    ]
                )

        elif operation == "update":

            if manager_info.name in {
                "pip",
                "pip3",
                "python-pip",
            }:

                command.extend(
                    [
                        "install",
                        "--upgrade",
                    ]
                )

            elif manager_info.name in {
                "npm",
                "pnpm",
                "yarn",
            }:

                command.append("update")

            elif manager_info.name in {
                "apt",
                "apt-get",
            }:

                command.extend(
                    [
                        "update",
                    ]
                )

            elif manager_info.name == "apk":

                command.append("upgrade")

            elif manager_info.name == "pacman":

                command.extend(
                    [
                        "-Syu",
                        "--noconfirm",
                    ]
                )

            elif manager_info.name == "winget":

                command.append("upgrade")

            elif manager_info.name == "choco":

                command.extend(
                    [
                        "upgrade",
                        "-y",
                    ]
                )

        elif operation == "search":

            if manager_info.name in {
                "pip",
                "pip3",
                "python-pip",
            }:

                command.append("index")
                command.append("versions")

            elif manager_info.name in {
                "npm",
                "pnpm",
                "yarn",
            }:

                command.append("search")

            elif manager_info.name in {
                "apt",
                "apt-get",
            }:

                command.append("search")

            elif manager_info.name == "apk":

                command.append("search")

            elif manager_info.name == "pacman":

                command.append("-Ss")

            elif manager_info.name == "winget":

                command.append("search")

            elif manager_info.name == "choco":

                command.append("search")

        else:

            raise PackageOperationError(
                f"Unsupported operation: {operation}"
            )

        if package:

            command.append(package)

        if extra_args:

            command.extend(
                str(argument)
                for argument in extra_args
            )

        return command

    # -----------------------------------------------------------------------
    # Security
    # -----------------------------------------------------------------------

    def _check_command(
        self,
        command: Sequence[str],
    ) -> None:

        command_text = " ".join(
            str(argument)
            for argument in command
        )

        try:

            check_command(
                command_text
            )

        except SecurityError as exc:

            raise PackagePermissionError(
                str(exc)
            ) from exc

    # -----------------------------------------------------------------------
    # Execution
    # ----------------------------------------------------------------------
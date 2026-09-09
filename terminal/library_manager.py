"""
Convexity Library Manager
Version: 1.0.0

Manages Convexity-specific libraries and tools.

Responsibilities:
- Install libraries/tools from trusted GitHub sources.
- Install libraries/tools from local archives/directories.
- Maintain an installed-library registry.
- Validate library manifests.
- Calculate SHA-256 checksums.
- Safely extract ZIP/TAR archives.
- Remove installed libraries.
- Inspect installed libraries.

Important:
This module does NOT automatically execute downloaded code.

OS-level package management belongs to package_manager.py.
Maple approval belongs to approval.py.

Architecture:

    Maple
      |
      v
    Approval
      |
      v
    LibraryManager
      |
      +---- GitHub
      |
      +---- Local source
      |
      v
    ~/.convexity/libraries/
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


__version__ = "1.0.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LibraryManagerError(Exception):
    """Base library manager error."""


class LibraryValidationError(LibraryManagerError):
    """Raised when a library manifest is invalid."""


class LibraryNotFoundError(LibraryManagerError):
    """Raised when a library cannot be found."""


class LibraryAlreadyInstalledError(LibraryManagerError):
    """Raised when a library already exists."""


class LibrarySecurityError(LibraryManagerError):
    """Raised when a potentially unsafe operation is detected."""


class LibraryInstallError(LibraryManagerError):
    """Raised when installation fails."""


# ---------------------------------------------------------------------------
# GitHub source
# ---------------------------------------------------------------------------

@dataclass
class GitHubSource:
    """
    Describes a GitHub repository source.

    Example:

        GitHubSource(
            owner="cckelvin",
            repository="Convexity",
            branch="main",
            path="libraries/example",
        )
    """

    owner: str
    repository: str
    branch: str = "main"
    path: str = ""

    def validate(self) -> None:
        if not self.owner:
            raise LibraryValidationError(
                "GitHub owner cannot be empty."
            )

        if not self.repository:
            raise LibraryValidationError(
                "GitHub repository cannot be empty."
            )

        if not self.branch:
            raise LibraryValidationError(
                "GitHub branch cannot be empty."
            )

        if any(
            value.startswith("/")
            for value in (self.path,)
        ):
            raise LibrarySecurityError(
                "GitHub source path cannot be absolute."
            )

        if ".." in Path(self.path).parts:
            raise LibrarySecurityError(
                "GitHub source path cannot contain '..'."
            )

    @property
    def repository_url(self) -> str:
        self.validate()

        return (
            "https://github.com/"
            f"{self.owner}/"
            f"{self.repository}"
        )

    @property
    def raw_url(self) -> str:
        self.validate()

        path = self.path.strip("/")

        if path:
            return (
                "https://raw.githubusercontent.com/"
                f"{self.owner}/"
                f"{self.repository}/"
                f"{self.branch}/"
                f"{path}"
            )

        return (
            "https://github.com/"
            f"{self.owner}/"
            f"{self.repository}/"
            f"archive/refs/heads/"
            f"{self.branch}.zip"
        )


# ---------------------------------------------------------------------------
# Library manifest
# ---------------------------------------------------------------------------

@dataclass
class LibraryManifest:
    """
    Metadata describing a Convexity library/tool.
    """

    name: str

    version: str

    description: str = ""

    kind: str = "library"

    entrypoint: Optional[str] = None

    source_type: str = "local"

    source: Optional[str] = None

    repository: Optional[str] = None

    license: Optional[str] = None

    dependencies: list[str] = field(
        default_factory=list
    )

    commands: list[str] = field(
        default_factory=list
    )

    checksum: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def validate(self) -> None:
        if not self.name:
            raise LibraryValidationError(
                "Library name cannot be empty."
            )

        if not self.version:
            raise LibraryValidationError(
                "Library version cannot be empty."
            )

        allowed_kinds = {
            "library",
            "tool",
            "plugin",
            "runtime",
            "model",
            "flow",
            "other",
        }

        if self.kind not in allowed_kinds:
            raise LibraryValidationError(
                f"Unsupported library kind: {self.kind}"
            )

        allowed_sources = {
            "local",
            "github",
            "url",
        }

        if self.source_type not in allowed_sources:
            raise LibraryValidationError(
                f"Unsupported source type: "
                f"{self.source_type}"
            )

        if self.entrypoint:
            self._validate_relative_path(
                self.entrypoint
            )

        for dependency in self.dependencies:
            if not dependency.strip():
                raise LibraryValidationError(
                    "Dependencies cannot contain empty values."
                )

    @staticmethod
    def _validate_relative_path(
        value: str,
    ) -> None:

        path = Path(value)

        if path.is_absolute():
            raise LibrarySecurityError(
                f"Absolute path is not allowed: {value}"
            )

        if ".." in path.parts:
            raise LibrarySecurityError(
                f"Path traversal is not allowed: {value}"
            )


# ---------------------------------------------------------------------------
# Installed library
# ---------------------------------------------------------------------------

@dataclass
class InstalledLibrary:
    """
    Record of an installed Convexity library.
    """

    name: str

    version: str

    kind: str

    install_path: str

    installed_at: float

    source_type: str

    source: Optional[str] = None

    checksum: Optional[str] = None

    entrypoint: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "InstalledLibrary":

        return cls(
            name=str(data["name"]),
            version=str(data["version"]),
            kind=str(data["kind"]),
            install_path=str(data["install_path"]),
            installed_at=float(
                data["installed_at"]
            ),
            source_type=str(
                data["source_type"]
            ),
            source=data.get("source"),
            checksum=data.get("checksum"),
            entrypoint=data.get("entrypoint"),
            metadata=dict(
                data.get("metadata", {})
            ),
        )


# ---------------------------------------------------------------------------
# Installation result
# ---------------------------------------------------------------------------

@dataclass
class LibraryResult:
    """
    Result of a library operation.
    """

    success: bool

    name: str

    version: Optional[str] = None

    message: str = ""

    path: Optional[str] = None

    checksum: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Library manager
# ---------------------------------------------------------------------------

class LibraryManager:
    """
    Manages Convexity libraries and tools.

    Nothing downloaded by this class is executed automatically.
    """

    REGISTRY_VERSION = 1

    MANIFEST_FILENAME = (
        "convexity-library.json"
    )

    DEFAULT_TRUSTED_HOSTS = {
        "github.com",
        "raw.githubusercontent.com",
    }

    def __init__(
        self,
        root: Optional[str | Path] = None,
        registry_path: Optional[str | Path] = None,
        trusted_hosts: Optional[set[str]] = None,
    ):

        if root is None:
            root = (
                Path.home()
                / ".convexity"
                / "libraries"
            )

        self.root = Path(root).expanduser().resolve()

        if registry_path is None:
            registry_path = (
                Path.home()
                / ".convexity"
                / "libraries.json"
            )

        self.registry_path = (
            Path(registry_path)
            .expanduser()
            .resolve()
        )

        self.trusted_hosts = set(
            trusted_hosts
            or self.DEFAULT_TRUSTED_HOSTS
        )

        self._libraries: dict[
            str,
            InstalledLibrary,
        ] = {}

        self._ensure_directories()
        self._load_registry()

    # -----------------------------------------------------------------------
    # Directories
    # -----------------------------------------------------------------------

    def _ensure_directories(self) -> None:

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # -----------------------------------------------------------------------
    # Registry
    # -----------------------------------------------------------------------

    def _load_registry(self) -> None:

        if not self.registry_path.exists():
            self._libraries = {}
            return

        try:

            data = json.loads(
                self.registry_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:

            raise LibraryManagerError(
                "Unable to read library registry."
            ) from exc

        libraries = data.get(
            "libraries",
            {},
        )

        self._libraries = {}

        for name, value in libraries.items():

            try:

                self._libraries[name] = (
                    InstalledLibrary.from_dict(
                        value
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:

                raise LibraryManagerError(
                    f"Invalid registry entry: {name}"
                ) from exc

    def _save_registry(self) -> None:

        payload = {
            "registry_version": (
                self.REGISTRY_VERSION
            ),
            "libraries": {
                name: library.to_dict()
                for name, library
                in self._libraries.items()
            },
        }

        temporary = (
            self.registry_path.with_suffix(
                ".tmp"
            )
        )

        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        temporary.replace(
            self.registry_path
        )

    # -----------------------------------------------------------------------
    # Names
    # -----------------------------------------------------------------------

    @staticmethod
    def validate_name(
        name: str,
    ) -> str:

        name = name.strip()

        if not name:
            raise LibraryValidationError(
                "Library name cannot be empty."
            )

        if len(name) > 128:
            raise LibraryValidationError(
                "Library name is too long."
            )

        allowed = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "-_."
        )

        if any(
            character not in allowed
            for character in name
        ):
            raise LibraryValidationError(
                "Library names may only contain "
                "letters, numbers, '-', '_' and '.'."
            )

        return name

    # -----------------------------------------------------------------------
    # Manifest
    # -----------------------------------------------------------------------

    def validate_manifest(
        self,
        manifest: LibraryManifest,
    ) -> LibraryManifest:

        manifest.validate()

        manifest.name = self.validate_name(
            manifest.name
        )

        return manifest

    def load_manifest(
        self,
        directory: str | Path,
    ) -> LibraryManifest:

        directory = Path(
            directory
        ).resolve()

        manifest_path = (
            directory
            / self.MANIFEST_FILENAME
        )

        if not manifest_path.exists():
            raise LibraryValidationError(
                f"Manifest not found: "
                f"{manifest_path}"
            )

        try:

            data = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:

            raise LibraryValidationError(
                "Unable to read library manifest."
            ) from exc

        manifest = LibraryManifest(
            name=str(
                data.get("name", "")
            ),
            version=str(
                data.get("version", "")
            ),
            description=str(
                data.get("description", "")
            ),
            kind=str(
                data.get(
                    "kind",
                    "library",
                )
            ),
            entrypoint=data.get(
                "entrypoint"
            ),
            source_type=str(
                data.get(
                    "source_type",
                    "local",
                )
            ),
            source=data.get("source"),
            repository=data.get(
                "repository"
            ),
            license=data.get(
                "license"
            ),
            dependencies=list(
                data.get(
                    "dependencies",
                    [],
                )
            ),
            commands=list(
                data.get(
                    "commands",
                    [],
                )
            ),
            checksum=data.get(
                "checksum"
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

        return self.validate_manifest(
            manifest
        )

    # -----------------------------------------------------------------------
    # Checksums
    # -----------------------------------------------------------------------

    @staticmethod
    def sha256_file(
        path: str | Path,
        chunk_size: int = 1024 * 1024,
    ) -> str:

        path = Path(path)

        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        digest = hashlib.sha256()

        with path.open("rb") as handle:

            while True:

                chunk = handle.read(
                    chunk_size
                )

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    @classmethod
    def sha256_directory(
        cls,
        directory: str | Path,
    ) -> str:

        directory = Path(directory)

        if not directory.is_dir():
            raise NotADirectoryError(
                directory
            )

        digest = hashlib.sha256()

        files = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file()
        )

        for path in files:

            relative = path.relative_to(
                directory
            )

            digest.update(
                str(relative)
                .replace(
                    os.sep,
                    "/",
                )
                .encode("utf-8")
            )

            digest.update(b"\0")

            with path.open("rb") as handle:

                while True:

                    chunk = handle.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    digest.update(chunk)

        return digest.hexdigest()

    # -----------------------------------------------------------------------
    # Safe paths
    # -----------------------------------------------------------------------

    @staticmethod
    def _safe_join(
        root: Path,
        relative: str | Path,
    ) -> Path:

        root = root.resolve()

        target = (
            root / Path(relative)
        ).resolve()

        try:
            target.relative_to(root)

        except ValueError as exc:

            raise LibrarySecurityError(
                f"Path escapes extraction root: "
                f"{relative}"
            ) from exc

        return target

    # -----------------------------------------------------------------------
    # Archive extraction
    # -----------------------------------------------------------------------

    def _extract_zip(
        self,
        archive: Path,
        destination: Path,
    ) -> None:

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        with zipfile.ZipFile(
            archive,
            "r",
        ) as archive_file:

            for member in archive_file.infolist():

                target = self._safe_join(
                    destination,
                    member.filename,
                )

                if member.is_dir():

                    target.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    continue

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with (
                    archive_file.open(member)
                    as source,
                    target.open("wb")
                    as output
                ):
                    shutil.copyfileobj(
                        source,
                        output,
                    )

    def _extract_tar(
        self,
        archive: Path,
        destination: Path,
    ) -> None:

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        with tarfile.open(
            archive,
            "r:*",
        ) as archive_file:

            for member in archive_file.getmembers():

                target = self._safe_join(
                    destination,
                    member.name,
                )

                if member.isdir():

                    target.mkdir(
                        parents=True,
                   
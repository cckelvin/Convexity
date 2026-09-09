"""
Convexity Filesystem Engine
Version 0.2.0

Provides Convexity-native filesystem operations:

- pwd
- ls
- cd
- mkdir
- touch
- cat
- write
- append
- rm
- copy
- move
- exists
- file/directory detection
- recursive search
- glob
- metadata
- file sizes
- directory sizes
- rename
- safe path validation

All filesystem access passes through Convexity's security layer.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Optional

from .config import config
from .security import (
    PermissionDenied,
    SecurityError,
    check_file_operation,
    check_permission,
    validate_path,
)


# ---------------------------------------------------------------------------
# FILE INFORMATION
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """Structured information about a filesystem object."""

    path: str
    name: str
    type: str
    size: int
    modified: float
    permissions: str
    hidden: bool

    @property
    def is_file(self) -> bool:
        return self.type == "file"

    @property
    def is_directory(self) -> bool:
        return self.type == "directory"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "modified": self.modified,
            "permissions": self.permissions,
            "hidden": self.hidden,
        }


# ---------------------------------------------------------------------------
# CURRENT DIRECTORY
# ---------------------------------------------------------------------------

def get_current_directory() -> Path:
    """Return Convexity's current working directory."""

    return Path.cwd()


def get_current_directory_string() -> str:
    """Return the current directory as a string."""

    return str(get_current_directory())


def change_directory(path: str) -> Path:
    """
    Change Convexity's process working directory.

    The terminal integration layer can later replace this with a
    per-session virtual working directory.
    """

    target = validate_path(
        path,
        must_exist=True,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    os.chdir(target)

    return target


# ---------------------------------------------------------------------------
# DIRECTORY OPERATIONS
# ---------------------------------------------------------------------------

def list_directory(
    path: str = ".",
    *,
    show_hidden: bool = False,
    recursive: bool = False,
) -> List[FileInfo]:
    """
    List directory contents.

    Examples:

        list_directory(".")
        list_directory(".", show_hidden=True)
        list_directory(".", recursive=True)
    """

    target = validate_path(
        path,
        must_exist=True,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    results: List[FileInfo] = []

    if recursive:
        iterator = target.rglob("*")
    else:
        iterator = target.iterdir()

    for item in iterator:

        if not show_hidden and is_hidden(item):
            continue

        try:
            results.append(get_file_info(item))
        except OSError:
            # A disappearing or inaccessible file should not break ls.
            continue

    results.sort(
        key=lambda item: (
            item.type != "directory",
            item.name.lower(),
        )
    )

    return results


def make_directory(
    path: str,
    *,
    parents: bool = True,
    exist_ok: bool = True,
) -> Path:
    """Create a directory."""

    target = validate_path(
        path,
        allow_missing=True,
    )

    target.mkdir(
        parents=parents,
        exist_ok=exist_ok,
    )

    return target


# ---------------------------------------------------------------------------
# FILE CREATION / READING / WRITING
# ---------------------------------------------------------------------------

def touch_file(path: str) -> Path:
    """Create an empty file if it does not exist."""

    target = validate_path(
        path,
        allow_missing=True,
    )

    if target.exists() and target.is_dir():
        raise SecurityError(
            f"Cannot touch a directory: {target}"
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.touch(
        exist_ok=True,
    )

    return target


def read_file(
    path: str,
    *,
    encoding: str = "utf-8",
    max_bytes: Optional[int] = None,
) -> str:
    """
    Read a text file.

    Large files are limited to prevent accidental memory exhaustion.
    """

    target = validate_path(
        path,
        must_exist=True,
    )

    if not target.is_file():
        raise SecurityError(
            f"Not a file: {target}"
        )

    limit = (
        max_bytes
        if max_bytes is not None
        else config.MAX_FILE_READ_SIZE
    )

    try:
        with target.open(
            "r",
            encoding=encoding,
            errors="replace",
        ) as file:

            content = file.read(limit)

    except UnicodeDecodeError as exc:
        raise SecurityError(
            f"Unable to decode file as {encoding}: {target}"
        ) from exc

    if target.stat().st_size > limit:
        content += (
            "\n\n[File output truncated by Convexity]"
        )

    return content


def write_file(
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
    overwrite: bool = True,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """
    Write text to a file.

    Existing files require overwrite permission.
    """

    if not isinstance(content, str):
        raise SecurityError(
            "File content must be a string."
        )

    target = check_file_operation(
        "overwrite" if Path(path).exists() else "write",
        path,
        source=source,
        confirmed=confirmed,
    )

    if target.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {target}"
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        content,
        encoding=encoding,
    )

    return target


def append_file(
    path: str,
    content: str,
    *,
    encoding: str = "utf-8",
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Append text to a file."""

    target = validate_path(
        path,
        allow_missing=True,
    )

    if target.exists():
        check_permission(
            "overwrite",
            source=source,
            confirmed=confirmed,
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with target.open(
        "a",
        encoding=encoding,
    ) as file:
        file.write(content)

    return target


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def delete_path(
    path: str,
    *,
    recursive: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> bool:
    """
    Delete a file or directory.

    Recursive directory deletion is explicitly permission-controlled.
    """

    target = check_file_operation(
        "delete",
        path,
        source=source,
        confirmed=confirmed,
    )

    if not target.exists():
        return False

    if target.is_symlink():
        target.unlink()
        return True

    if target.is_file():
        target.unlink()
        return True

    if target.is_dir():

        if recursive:
            check_permission(
                "delete",
                source=source,
                confirmed=confirmed,
            )

            shutil.rmtree(target)
            return True

        try:
            target.rmdir()
            return True
        except OSError as exc:
            raise SecurityError(
                f"Directory is not empty. "
                f"Use recursive deletion with confirmation: {target}"
            ) from exc

    raise SecurityError(
        f"Unsupported filesystem object: {target}"
    )


# ---------------------------------------------------------------------------
# COPY / MOVE / RENAME
# ---------------------------------------------------------------------------

def copy_path(
    source_path: str,
    destination: str,
    *,
    overwrite: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Copy a file or directory."""

    source_target = validate_path(
        source_path,
        must_exist=True,
    )

    destination_target = validate_path(
        destination,
        allow_missing=True,
    )

    if destination_target.exists():

        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: {destination_target}"
            )

        check_permission(
            "overwrite",
            source=source,
            confirmed=confirmed,
        )

    destination_target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if source_target.is_dir():

        shutil.copytree(
            source_target,
            destination_target,
            dirs_exist_ok=overwrite,
        )

    else:

        shutil.copy2(
            source_target,
            destination_target,
        )

    return destination_target


def move_path(
    source_path: str,
    destination: str,
    *,
    overwrite: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Move a file or directory."""

    source_target = validate_path(
        source_path,
        must_exist=True,
    )

    destination_target = validate_path(
        destination,
        allow_missing=True,
    )

    if destination_target.exists():

        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: {destination_target}"
            )

        check_permission(
            "overwrite",
            source=source,
            confirmed=confirmed,
        )

    destination_target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.move(
        str(source_target),
        str(destination_target),
    )

    return destination_target


def rename_path(
    path: str,
    new_name: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Rename a filesystem object."""

    target = validate_path(
        path,
        must_exist=True,
    )

    if not new_name or "/" in new_name or "\\" in new_name:
        raise SecurityError(
            "New name must be a single filename."
        )

    destination = target.parent / new_name

    destination = validate_path(
        destination,
        allow_missing=True,
    )

    if destination.exists():
        check_permission(
            "overwrite",
            source=source,
            confirmed=confirmed,
        )

    target.rename(destination)

    return destination


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

def search_files(
    path: str = ".",
    pattern: str = "*",
    *,
    recursive: bool = True,
    files_only: bool = False,
    directories_only: bool = False,
) -> List[Path]:
    """
    Search for files/directories using wildcard matching.

    Examples:

        search_files(".", "*.py")
        search_files(".", "*.json")
        search_files(".", "README*")
    """

    target = validate_path(
        path,
        must_exist=True,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Search root is not a directory: {target}"
        )

    iterator = (
        target.rglob("*")
        if recursive
        else target.iterdir()
    )

    results: List[Path] = []

    for item in iterator:

        if not fnmatch.fnmatch(
            item.name,
            pattern,
        ):
            continue

        if files_only and not item.is_file():
            continue

        if directories_only and not item.is_dir():
            continue

        results.append(item)

    return sorted(
        results,
        key=lambda value: str(value).lower(),
    )


def find_text(
    path: str = ".",
    text: str = "",
    *,
    recursive: bool = True,
    case_sensitive: bool = False,
) -> List[tuple[Path, int, str]]:
    """
    Search text inside files.

    Returns:

        (file_path, line_number, matching_line)
    """

    if not text:
        raise SecurityError(
            "Search text cannot be empty."
        )

    target = validate_path(
        path,
        must_exist=True,
    )

    if target.is_file():
        candidates = [target]

    else:
        iterator = (
            target.rglob("*")
            if recursive
            else target.iterdir()
        )

        candidates = [
            item
            for item in iterator
            if item.is_file()
        ]

    results = []

    needle = (
        text
        if case_sensitive
        else text.lower()
    )

    for file_path in candidates:

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:

                for number, line in enumerate(
                    file,
                    start=1,
                ):

                    haystack = (
                        line
                        if case_sensitive
                        else line.lower()
                    )

                    if needle in haystack:
                        results.append(
                            (
                                file_path,
                                number,
                                line.rstrip("\n"),
                            )
                        )

        except (OSError, UnicodeError):
            continue

    return results


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

def get_file_info(
    path: str | Path,
) -> FileInfo:
    """Return structured filesystem metadata."""

    target = validate_path(
        path,
        must_exist=True,
    )

    information = target.stat()

    if target.is_dir():
        object_type = "directory"
    elif target.is_file():
        object_type = "file"
    elif target.is_symlink():
        object_type = "symlink"
    else:
        object_type = "other"

    return FileInfo(
        path=str(target),
        name=target.name,
        type=object_type,
        size=information.st_size,
        modified=information.st_mtime,
        permissions=stat.filemode(
            information.st_mode
        ),
        hidden=is_hidden(target),
    )


def get_file_size(path: str | Path) -> int:
    """Return file size in bytes."""

    target = validate_path(
        path,
        must_exist=True,
    )

    return target.stat().st_size


def get_directory_size(path: str | Path) -> int:
    """Calculate total size of files under a directory."""

    target = validate_path(
        path,
        must_exist=True,
    )

    if target.is_file():
        return target.stat().st_size

    total = 0

    for item in target.rglob("*"):

        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue

    return total


# ---------------------------------------------------------------------------
# EXISTENCE / TYPE
# ---------------------------------------------------------------------------

def exists(path: str | Path) -> bool:
    """Return whether a path exists."""

    try:
        return validate_path(
            path,
            allow_missing=True,
        ).exists()

    except SecurityError:
        return False


def is_file(path: str | Path) -> bool:
    """Return whether a path is a file."""

    try:
        return validate_path(
            path,
            must_exist=True,
        ).is_file()

    except SecurityError:
        return False


def is_directory(path: str | Path) -> bool:
    """Return whether a path is a directory."""

    try:
        return validate_path(
            path,
            must_exist=True,
        ).is_dir()

    except SecurityError:
        return False


def is_hidden(path: str | Path) -> bool:
    """Determine whether a filesystem object is hidden."""

    target = Path(path)

    # Unix hidden-file convention.
    if target.name.startswith("."):
        return True

    # Windows hidden attribute.
    if os.name == "nt" and target.exists():

        try:
            attributes = getattr(
                target.stat(),
                "st_file_attributes",
                0,
            )

            return bool(
                attributes & getattr(
                    stat,
                    "FILE_ATTRIBUTE_HIDDEN",
                    0x2,
                )
            )

        except OSError:
            return False

    return False


# ---------------------------------------------------------------------------
# DIRECTORY WALK
# ---------------------------------------------------------------------------

def walk(
    path: str = ".",
) -> Generator[tuple[str, List[str], List[str]], None, None]:
    """
    Walk a directory tree.

    Yields:

        root, directories, files
    """

    target = validate_path(
        path,
        must_exist=True,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Walk root is not a directory: {target}"
        )

    for root, directories, files in os.walk(target):
        yield root, directories, files


# ---------------------------------------------------------------------------
# PATH UTILITIES
# ---------------------------------------------------------------------------

def absolute_path(path: str) -> Path:
    """Return a validated absolute path."""

    return validate_path(
        path,
        allow_missing=True,
    )


def parent_directory(path: str) -> Path:
    """Return the validated parent directory."""

    target = validate_path(
        path,
        allow_missing=True,
    )

    return validate_path(
        target.parent,
        allow_missing=True,
    )


# ---------------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------------

__all__ = [
    "FileInfo",
    "get_current_directory",
    "get_current_directory_string",
    "change_directory",
    "list_directory",
    "make_directory",
    "touch_file",
    "read_file",
    "write_file",
    "append_file",
    "delete_path",
    "copy_path",
    "move_path",
    "rename_path",
    "search_files",
    "find_text",
    "get_file_info",
    "get_file_size",
    "get_directory_size",
    "exists",
    "is_file",
    "is_directory",
    "is_hidden",
    "walk",
    "absolute_path",
    "parent_directory",
]
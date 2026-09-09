"""
Convexity Native Filesystem Engine
Version 1.0.0

Responsibilities:
- Native filesystem operations
- Path resolution
- Directory listing
- File creation and reading
- File writing and appending
- Copy / move / rename
- Delete
- Search / grep
- Metadata
- File and directory sizes
- Existence checks
- Session-relative path support

Architecture:
    TerminalSession owns the current working directory.
    Filesystem owns filesystem operations.

This module NEVER changes the process-wide cwd with os.chdir().
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

from .config import config
from .security import (
    SecurityError,
    check_file_operation,
    check_permission,
    validate_path,
)


# ============================================================================
# FILE INFORMATION
# ============================================================================


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

    @property
    def is_symlink(self) -> bool:
        return self.type == "symlink"

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


# ============================================================================
# PATH RESOLUTION
# ============================================================================


def resolve_path(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
    must_exist: bool = False,
    allow_missing: bool = True,
) -> Path:
    """
    Resolve a path relative to an optional session cwd.

    This is the primary path-resolution function used by the filesystem
    engine.

    Example:

        resolve_path("app.py", cwd="/project")

    ->

        /project/app.py
    """

    if path is None:
        raise SecurityError("Path cannot be None.")

    raw = str(path).strip()

    if not raw:
        raise SecurityError("Path cannot be empty.")

    path_obj = Path(raw).expanduser()

    if not path_obj.is_absolute() and cwd is not None:
        path_obj = Path(cwd).expanduser() / path_obj

    return validate_path(
        path_obj,
        must_exist=must_exist,
        allow_missing=allow_missing,
    )


def get_current_directory() -> Path:
    """
    Return the process cwd.

    Session-aware callers should normally use TerminalSession.cwd instead.
    """

    return Path.cwd()


def get_current_directory_string() -> str:
    """Return the process cwd as a string."""

    return str(get_current_directory())


def change_directory(
    path: str,
    *,
    cwd: str | Path | None = None,
) -> Path:
    """
    Validate a directory and return the new path.

    IMPORTANT:
        This does NOT call os.chdir().

    TerminalSession is responsible for storing the new cwd.
    """

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    return target


# ============================================================================
# DIRECTORY OPERATIONS
# ============================================================================


def list_directory(
    path: str = ".",
    *,
    cwd: str | Path | None = None,
    show_hidden: bool = False,
    recursive: bool = False,
) -> List[FileInfo]:
    """List the contents of a directory."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    iterator: Iterator[Path]

    if recursive:
        iterator = target.rglob("*")
    else:
        iterator = target.iterdir()

    results: List[FileInfo] = []

    for item in iterator:
        if not show_hidden and is_hidden(item):
            continue

        try:
            results.append(get_file_info(item))
        except OSError:
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
    cwd: str | Path | None = None,
    parents: bool = True,
    exist_ok: bool = True,
) -> Path:
    """Create a directory."""

    target = resolve_path(
        path,
        cwd=cwd,
        allow_missing=True,
    )

    target.mkdir(
        parents=parents,
        exist_ok=exist_ok,
    )

    return target


# ============================================================================
# FILE CREATION
# ============================================================================


def touch_file(
    path: str,
    *,
    cwd: str | Path | None = None,
) -> Path:
    """Create an empty file if it does not exist."""

    target = resolve_path(
        path,
        cwd=cwd,
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

    target.touch(exist_ok=True)

    return target


# ============================================================================
# FILE READING
# ============================================================================


def read_file(
    path: str,
    *,
    cwd: str | Path | None = None,
    encoding: str = "utf-8",
    max_bytes: Optional[int] = None,
) -> str:
    """Read a text file with a configurable size limit."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
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

    if limit <= 0:
        raise SecurityError(
            "File read limit must be greater than zero."
        )

    try:
        with target.open(
            "r",
            encoding=encoding,
            errors="replace",
        ) as file:
            content = file.read(limit)

    except OSError as exc:
        raise SecurityError(
            f"Unable to read file: {target}"
        ) from exc

    if target.stat().st_size > limit:
        content += (
            "\n\n[File output truncated by Convexity]"
        )

    return content


# ============================================================================
# FILE WRITING
# ============================================================================


def write_file(
    path: str,
    content: str,
    *,
    cwd: str | Path | None = None,
    encoding: str = "utf-8",
    overwrite: bool = True,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Write text to a file."""

    if not isinstance(content, str):
        raise SecurityError(
            "File content must be a string."
        )

    target = resolve_path(
        path,
        cwd=cwd,
        allow_missing=True,
    )

    if target.exists():
        check_file_operation(
            "overwrite",
            target,
            source=source,
            confirmed=confirmed,
        )

        if not overwrite:
            raise FileExistsError(
                f"File already exists: {target}"
            )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        target.write_text(
            content,
            encoding=encoding,
        )
    except OSError as exc:
        raise SecurityError(
            f"Unable to write file: {target}"
        ) from exc

    return target


def append_file(
    path: str,
    content: str,
    *,
    cwd: str | Path | None = None,
    encoding: str = "utf-8",
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Append text to a file."""

    if not isinstance(content, str):
        raise SecurityError(
            "File content must be a string."
        )

    target = resolve_path(
        path,
        cwd=cwd,
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

    try:
        with target.open(
            "a",
            encoding=encoding,
        ) as file:
            file.write(content)

    except OSError as exc:
        raise SecurityError(
            f"Unable to append to file: {target}"
        ) from exc

    return target


# ============================================================================
# DELETE
# ============================================================================


def delete_path(
    path: str,
    *,
    cwd: str | Path | None = None,
    recursive: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> bool:
    """
    Delete a file or directory.

    Recursive directory deletion requires explicit confirmation when
    the source is Maple.
    """

    target = resolve_path(
        path,
        cwd=cwd,
        allow_missing=True,
    )

    if not target.exists() and not target.is_symlink():
        return False

    check_file_operation(
        "delete",
        target,
        source=source,
        confirmed=confirmed,
    )

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
                "Directory is not empty. "
                "Use recursive deletion if intended."
            ) from exc

    raise SecurityError(
        f"Unsupported filesystem object: {target}"
    )


# ============================================================================
# COPY
# ============================================================================


def copy_path(
    source_path: str,
    destination: str,
    *,
    cwd: str | Path | None = None,
    overwrite: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Copy a file or directory."""

    source_target = resolve_path(
        source_path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    destination_target = resolve_path(
        destination,
        cwd=cwd,
        allow_missing=True,
    )

    if destination_target.exists():

        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: "
                f"{destination_target}"
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

    try:
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

    except OSError as exc:
        raise SecurityError(
            f"Unable to copy '{source_target}' "
            f"to '{destination_target}'"
        ) from exc

    return destination_target


# ============================================================================
# MOVE
# ============================================================================


def move_path(
    source_path: str,
    destination: str,
    *,
    cwd: str | Path | None = None,
    overwrite: bool = False,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Move a file or directory."""

    source_target = resolve_path(
        source_path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    destination_target = resolve_path(
        destination,
        cwd=cwd,
        allow_missing=True,
    )

    if destination_target.exists():

        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: "
                f"{destination_target}"
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

    try:
        shutil.move(
            str(source_target),
            str(destination_target),
        )

    except OSError as exc:
        raise SecurityError(
            f"Unable to move '{source_target}' "
            f"to '{destination_target}'"
        ) from exc

    return destination_target


# ============================================================================
# RENAME
# ============================================================================


def rename_path(
    path: str,
    new_name: str,
    *,
    cwd: str | Path | None = None,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """Rename a filesystem object."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if not new_name:
        raise SecurityError(
            "New name cannot be empty."
        )

    if (
        "/" in new_name
        or "\\" in new_name
        or new_name in {".", ".."}
    ):
        raise SecurityError(
            "New name must be a single filename."
        )

    destination = target.parent / new_name

    destination = resolve_path(
        destination,
        allow_missing=True,
    )

    if destination.exists():
        check_permission(
            "overwrite",
            source=source,
            confirmed=confirmed,
        )

    try:
        target.rename(destination)
    except OSError as exc:
        raise SecurityError(
            f"Unable to rename '{target}' "
            f"to '{destination}'"
        ) from exc

    return destination


# ============================================================================
# SEARCH
# ============================================================================


def search_files(
    path: str = ".",
    pattern: str = "*",
    *,
    cwd: str | Path | None = None,
    recursive: bool = True,
    files_only: bool = False,
    directories_only: bool = False,
) -> List[Path]:
    """
    Search for filesystem objects using wildcard matching.
    """

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
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
    cwd: str | Path | None = None,
    recursive: bool = True,
    case_sensitive: bool = False,
) -> List[tuple[Path, int, str]]:
    """
    Search for text inside files.

    Returns:

        (path, line_number, matching_line)
    """

    if not text:
        raise SecurityError(
            "Search text cannot be empty."
        )

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if target.is_file():
        candidates = [target]

    elif target.is_dir():

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

    else:
        raise SecurityError(
            f"Unsupported search target: {target}"
        )

    results: List[tuple[Path, int, str]] = []

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

                for line_number, line in enumerate(
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
                                line_number,
                                line.rstrip("\n"),
                            )
                        )

        except OSError:
            continue

    return results


# ============================================================================
# METADATA
# ============================================================================


def get_file_info(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> FileInfo:
    """Return metadata for a filesystem object."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    try:
        information = target.stat()
    except OSError as exc:
        raise SecurityError(
            f"Unable to inspect: {target}"
        ) from exc

    if target.is_symlink():
        object_type = "symlink"
    elif target.is_dir():
        object_type = "directory"
    elif target.is_file():
        object_type = "file"
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


def get_file_size(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> int:
    """Return the size of a filesystem object in bytes."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    try:
        return target.stat().st_size
    except OSError as exc:
        raise SecurityError(
            f"Unable to determine size: {target}"
        ) from exc


def get_directory_size(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> int:
    """Return the total size of files inside a directory."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    total = 0

    for item in target.rglob("*"):

        if not item.is_file():
            continue

        try:
            total += item.stat().st_size
        except OSError:
            continue

    return total


# ============================================================================
# EXISTENCE / TYPE
# ============================================================================


def exists(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> bool:
    """Return whether a path exists."""

    try:
        target = resolve_path(
            path,
            cwd=cwd,
            allow_missing=True,
        )

        return target.exists() or target.is_symlink()

    except SecurityError:
        return False


def is_file(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> bool:
    """Return whether a path is a file."""

    try:
        return resolve_path(
            path,
            cwd=cwd,
            must_exist=True,
            allow_missing=False,
        ).is_file()
    except SecurityError:
        return False


def is_directory(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
) -> bool:
    """Return whether a path is a directory."""

    try:
        return resolve_path(
            path,
            cwd=cwd,
            must_exist=True,
            allow_missing=False,
        ).is_dir()
    except SecurityError:
        return False


def is_hidden(path: str | Path) -> bool:
    """
    Determine whether a filesystem object is hidden.

    Unix:
        Names beginning with '.' are hidden.

    Windows:
        The hidden file attribute is checked when available.
    """

    target = Path(path)

    if target.name.startswith("."):
        return True

    if os.name == "nt":
        try:
            import ctypes

            attributes = ctypes.windll.kernel32.GetFileAttributesW(
                str(target)
            )

            if attributes != -1:
                FILE_ATTRIBUTE_HIDDEN = 0x2

                return bool(
                    attributes & FILE_ATTRIBUTE_HIDDEN
                )

        except Exception:
            pass

    return False


# ============================================================================
# GLOB
# ============================================================================


def glob(
    pattern: str,
    *,
    cwd: str | Path | None = None,
    recursive: bool = False,
) -> List[Path]:
    """
    Resolve a glob pattern relative to a session cwd.
    """

    base = (
        Path(cwd).expanduser()
        if cwd is not None
        else Path.cwd()
    )

    base = validate_path(
        base,
        must_exist=True,
        allow_missing=False,
    )

    if recursive:
        results = base.glob(pattern)
    else:
        results = base.glob(pattern)

    return sorted(
        results,
        key=lambda value: str(value).lower(),
    )


# ============================================================================
# DIRECTORY ITERATION
# ============================================================================


def iter_directory(
    path: str = ".",
    *,
    cwd: str | Path | None = None,
) -> Iterator[Path]:
    """Yield directory entries."""

    target = resolve_path(
        path,
        cwd=cwd,
        must_exist=True,
        allow_missing=False,
    )

    if not target.is_dir():
        raise SecurityError(
            f"Not a directory: {target}"
        )

    yield from target.iterdir()


# ============================================================================
# COMPATIBILITY ALIASES
# ============================================================================


# Common names used by the terminal/builtins layer.

ls = list_directory
mkdir = make_directory
touch = touch_file
cat = read_file
read = read_file
write = write_file
append = append_file
rm = delete_path
copy = copy_path
move = move_path
rename = rename_path
find = search_files
grep = find_text
stat_file = get_file_info


# ============================================================================
# PUBLIC API
# ============================================================================


__all__ = [
    "FileInfo",

    "resolve_path",

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

    "glob",
    "iter_directory",

    "ls",
    "mkdir",
    "touch",
    "cat",
    "read",
    "write",
    "append",
    "rm",
    "copy",
    "move",
    "rename",
    "find",
    "grep",
    "stat_file",
]

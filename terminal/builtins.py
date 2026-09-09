"""
Convexity Native Built-ins
Version 0.5.0

Native commands provided directly by Convexity.

These commands do not depend on Bash, PowerShell, CMD, or Termux.
"""

from __future__ import annotations

import os
import shutil
import platform
from dataclasses import dataclass
from typing import Callable, Optional

from .filesystem import (
    change_directory,
    list_directory,
    make_directory,
    touch_file,
    read_file,
    write_file,
    append_file,
    delete_path,
    copy_path,
    move_path,
    search_files,
    find_text,
    get_file_info,
    get_file_size,
    get_directory_size,
    exists,
    is_file,
    is_directory,
)
from .environment import (
    context,
    set_variable,
    get_variable,
    unset_variable,
    expand_variables,
    set_alias,
    get_alias,
    remove_alias,
)
from .executor import (
    list_processes,
    terminate_process,
    kill_process,
)


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass
class BuiltinResult:
    handled: bool
    success: bool = True
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


# ---------------------------------------------------------------------------
# BUILTIN
# ---------------------------------------------------------------------------

@dataclass
class Builtin:
    name: str
    handler: Callable
    description: str


# ---------------------------------------------------------------------------
# HELP
# ---------------------------------------------------------------------------

def builtin_help(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    lines = [
        "Convexity native commands:",
        "",
        "Navigation:",
        "  cd <path>              Change directory",
        "  pwd                    Show current directory",
        "  ls [path]              List directory",
        "",
        "Files:",
        "  cat <file>             Read file",
        "  write <file> <text>    Write file",
        "  append <file> <text>   Append to file",
        "  touch <file>           Create file",
        "  mkdir <path>            Create directory",
        "  rm <path>               Delete file/directory",
        "  cp <source> <dest>      Copy",
        "  mv <source> <dest>      Move",
        "",
        "Search:",
        "  find <path> [pattern]   Search files",
        "  grep <text> [path]      Search file contents",
        "",
        "Environment:",
        "  set [name] [value]      Set/list variables",
        "  unset <name>            Remove variable",
        "  env                     Show environment",
        "  alias [name] [command]  Create/list aliases",
        "  unalias <name>          Remove alias",
        "",
        "Processes:",
        "  jobs                    Show processes",
        "  kill <pid>              Terminate process",
        "  kill -9 <pid>           Force kill",
        "",
        "System:",
        "  whoami                  Current user",
        "  hostname                Computer name",
        "  sysinfo                 System information",
        "",
        "Shell:",
        "  history                 Command history",
        "  echo <text>             Print text",
        "  clear                   Clear terminal",
        "  exit                    Exit Convexity",
    ]

    return BuiltinResult(
        handled=True,
        stdout="\n".join(lines) + "\n",
    )


# ---------------------------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------------------------

def builtin_pwd(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return BuiltinResult(
        handled=True,
        stdout=os.getcwd() + "\n",
    )


def builtin_cd(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    path = args[0] if args else os.path.expanduser("~")

    path = expand_variables(path)

    try:

        new_path = change_directory(path)

        return BuiltinResult(
            handled=True,
            stdout=new_path + "\n",
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"cd: {exc}\n",
            return_code=1,
        )


def builtin_ls(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    path = "."

    show_hidden = False
    recursive = False

    for arg in args:

        if arg in ("-a", "--all"):
            show_hidden = True

        elif arg in ("-r", "--recursive"):
            recursive = True

        else:
            path = arg

    try:

        entries = list_directory(
            path,
            show_hidden=show_hidden,
            recursive=recursive,
        )

        lines = []

        for entry in entries:

            if isinstance(entry, dict):

                lines.append(
                    str(entry)
                )

            else:

                lines.append(
                    str(entry)
                )

        return BuiltinResult(
            handled=True,
            stdout="\n".join(lines)
            + ("\n" if lines else ""),
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"ls: {exc}\n",
            return_code=1,
        )


# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------

def builtin_cat(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="cat: missing file\n",
            return_code=1,
        )

    output = []

    try:

        for path in args:

            output.append(
                read_file(
                    expand_variables(path)
                )
            )

        return BuiltinResult(
            handled=True,
            stdout="".join(output),
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"cat: {exc}\n",
            return_code=1,
        )


def builtin_touch(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="touch: missing file\n",
            return_code=1,
        )

    try:

        for path in args:
            touch_file(
                expand_variables(path)
            )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"touch: {exc}\n",
            return_code=1,
        )


def builtin_mkdir(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="mkdir: missing directory\n",
            return_code=1,
        )

    try:

        for path in args:

            make_directory(
                expand_variables(path),
                parents=True,
            )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"mkdir: {exc}\n",
            return_code=1,
        )


def builtin_write(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="write: usage: write <file> <text>\n",
            return_code=1,
        )

    path = expand_variables(args[0])

    text = " ".join(args[1:])

    try:

        write_file(
            path,
            text,
        )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"write: {exc}\n",
            return_code=1,
        )


def builtin_append(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="append: usage: append <file> <text>\n",
            return_code=1,
        )

    path = expand_variables(args[0])

    text = " ".join(args[1:])

    try:

        append_file(
            path,
            text,
        )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"append: {exc}\n",
            return_code=1,
        )


def builtin_rm(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="rm: missing path\n",
            return_code=1,
        )

    recursive = False
    targets = []

    for arg in args:

        if arg in ("-r", "-R", "--recursive"):
            recursive = True
        else:
            targets.append(arg)

    try:

        for path in targets:

            delete_path(
                expand_variables(path),
                recursive=recursive,
                confirmed=kwargs.get(
                    "confirmed",
                    False,
                ),
            )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"rm: {exc}\n",
            return_code=1,
        )


def builtin_cp(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="cp: usage: cp <source> <destination>\n",
            return_code=1,
        )

    try:

        copy_path(
            expand_variables(args[0]),
            expand_variables(args[1]),
        )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"cp: {exc}\n",
            return_code=1,
        )


def builtin_mv(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="mv: usage: mv <source> <destination>\n",
            return_code=1,
        )

    try:

        move_path(
            expand_variables(args[0]),
            expand_variables(args[1]),
        )

        return BuiltinResult(
            handled=True
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"mv: {exc}\n",
            return_code=1,
        )


# ---------------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------------

def builtin_find(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    path = args[0] if args else "."
    pattern = args[1] if len(args) > 1 else "*"

    try:

        results = search_files(
            path,
            pattern=pattern,
        )

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(
                    str(item)
                    for item in results
                )
                + ("\n" if results else "")
            ),
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"find: {exc}\n",
            return_code=1,
        )


def builtin_grep(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="grep: missing search text\n",
            return_code=1,
        )

    text = args[0]

    path = args[1] if len(args) > 1 else "."

    try:

        results = find_text(
            path,
            text,
        )

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(
                    str(item)
                    for item in results
                )
                + ("\n" if results else "")
            ),
        )

    except Exception as exc:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"grep: {exc}\n",
            return_code=1,
        )


# ---------------------------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------------------------

def builtin_set(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        variables = context.environment.list_variables()

        lines = [
            f"{key}={value}"
            for key, value in variables.items()
        ]

        return BuiltinResult(
            handled=True,
            stdout="\n".join(lines)
            + ("\n" if lines else ""),
        )

    name = args[0]

    value = " ".join(args[1:]) if len(args) > 1 else ""

    result = set_variable(
        name,
        expand_variables(value),
    )

    if not result.success:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(
        handled=True
    )


def builtin_unset(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="unset: missing variable\n",
            return_code=1,
        )

    result = unset_variable(
        args[0]
    )

    if not result.success:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(
        handled=True
    )


def builtin_env(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    variables = context.environment.list_variables()

    lines = [
        f"{key}={value}"
        for key, value in variables.items()
    ]

    return BuiltinResult(
        handled=True,
        stdout="\n".join(lines)
        + ("\n" if lines else ""),
    )


# ---------------------------------------------------------------------------
# ALIASES
# ---------------------------------------------------------------------------

def builtin_alias(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        aliases = context.environment.list_aliases()

        lines = [
            f"{name}={value}"
            for name, value in aliases.items()
        ]

        return BuiltinResult(
            handled=True,
            stdout="\n".join(lines)
            + ("\n" if lines else ""),
        )

    if len(args) < 2:

        existing = get_alias(args[0])

        if existing is None:

            return BuiltinResult(
                handled=True,
                success=False,
                stderr=(
                    f"alias: '{args[0]}' not found\n"
                ),
                return_code=1,
            )

        return BuiltinResult(
            handled=True,
            stdout=(
                f"{args[0]}={existing}\n"
            ),
        )

    result = set_alias(
        args[0],
        " ".join(args[1:]),
    )

    if not result.success:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(
        handled=True
    )


def builtin_unalias(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr="unalias: missing alias\n",
            return_code=1,
        )

    result = remove_alias(
        args[0]
    )

    if not result.success:

        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(
        handled=True
    )


# ---------------------------------------------------------------------------
# PROCESSES
# ---------------------------------------------------------------------------

def builtin_jobs(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    processes = list_processes()

    lines = []

    for process in processes:

        lines.append(
            f"{process.pid}\t"
            f"{process
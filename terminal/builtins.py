"""
Convexity Native Built-ins
Version: 1.2.0

Native commands provided directly by Convexity.

These commands do not depend on Bash, PowerShell, CMD, or Termux.

Built-ins operate through Convexity's own:
- TerminalSession
- Filesystem
- ProcessManager
- Maple session state

The built-in layer does not create subprocesses directly.
"""

from __future__ import annotations

import getpass
import os
import platform
from dataclasses import dataclass
from typing import Callable, Optional

from .filesystem import (
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

from .process import (
    process_manager,
    ProcessState,
)

from .session import TerminalSession


__version__ = "1.2.0"


# ============================================================================
# RESULT TYPES
# ============================================================================

@dataclass
class BuiltinResult:
    """
    Result returned by a native Convexity built-in.
    """

    handled: bool

    success: bool = True

    stdout: str = ""

    stderr: str = ""

    return_code: int = 0


@dataclass
class Builtin:
    """
    Registered Convexity built-in command.
    """

    name: str

    handler: Callable

    description: str


# ============================================================================
# RESULT HELPERS
# ============================================================================

def _result(
    stdout: str = "",
    *,
    success: bool = True,
    stderr: str = "",
    return_code: int = 0,
) -> BuiltinResult:
    return BuiltinResult(
        handled=True,
        success=success,
        stdout=stdout,
        stderr=stderr,
        return_code=return_code,
    )


def _error(
    command: str,
    message: str,
    return_code: int = 1,
) -> BuiltinResult:
    return BuiltinResult(
        handled=True,
        success=False,
        stderr=f"{command}: {message}\n",
        return_code=return_code,
    )


# ============================================================================
# SESSION HELPERS
# ============================================================================

def _get_session(kwargs) -> Optional[TerminalSession]:
    session = kwargs.get("session")

    if isinstance(session, TerminalSession):
        return session

    return None


def _cwd(kwargs) -> str:
    session = _get_session(kwargs)

    if session is not None:
        return session.cwd

    return os.getcwd()


def _resolve_path(
    path: str,
    kwargs,
) -> str:
    """
    Resolve a path relative to the Convexity session.

    This function never calls os.chdir().
    """

    path = os.path.expandvars(path)
    path = os.path.expanduser(path)

    session = _get_session(kwargs)

    if session is None:
        return os.path.abspath(path)

    if os.path.isabs(path):
        return os.path.normpath(path)

    return os.path.normpath(
        os.path.join(
            session.cwd,
            path,
        )
    )


def _require_session(
    command: str,
    kwargs,
) -> Optional[BuiltinResult]:
    if _get_session(kwargs) is None:
        return _error(
            command,
            "No terminal session is attached.",
        )

    return None


# ============================================================================
# HELP
# ============================================================================

def builtin_help(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    lines = [
        "Convexity native commands:",
        "",
        "Navigation:",
        "  cd <path>               Change session directory",
        "  pwd                     Show current directory",
        "  ls [path]               List directory",
        "",
        "Files:",
        "  cat <file>              Read file",
        "  read <file>             Read file",
        "  write <file> <text>     Write file",
        "  append <file> <text>    Append to file",
        "  touch <file>            Create file",
        "  mkdir <path>            Create directory",
        "  rm <path>               Delete file/directory",
        "  del <path>              Delete file/directory",
        "  cp <source> <dest>      Copy",
        "  copy <source> <dest>    Copy",
        "  mv <source> <dest>      Move",
        "  move <source> <dest>    Move",
        "  stat <path>             Show file information",
        "  exists <path>           Check whether path exists",
        "",
        "Search:",
        "  find <path> [pattern]   Search files",
        "  grep <text> [path]      Search file contents",
        "",
        "Environment:",
        "  set [name] [value]      Set/list session variable",
        "  unset <name>            Remove variable",
        "  env                     Show session environment",
        "  alias [name] [command]  Create/list aliases",
        "  unalias <name>          Remove alias",
        "",
        "Processes:",
        "  jobs                    Show managed processes",
        "  ps                      Show managed processes",
        "  kill <id>               Terminate process",
        "  kill -9 <id>            Force kill process",
        "",
        "System:",
        "  whoami                  Current user",
        "  hostname                Computer name",
        "  sysinfo                 System information",
        "",
        "Maple:",
        "  load maple              Activate Maple",
        "  kill maple              Deactivate Maple",
        "",
        "Shell:",
        "  history                 Command history",
        "  echo <text>             Print text",
        "  clear                   Clear terminal",
        "  exit                    Exit Convexity",
    ]

    return _result(
        "\n".join(lines) + "\n"
    )


# ============================================================================
# NAVIGATION
# ============================================================================

def builtin_pwd(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return _result(
        _cwd(kwargs) + "\n"
    )


def builtin_cd(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "cd",
            "No terminal session is attached.",
        )

    path = (
        args[0]
        if args
        else "~"
    )

    try:
        target = _resolve_path(
            path,
            kwargs,
        )

        new_directory = session.change_directory(
            target
        )

        return _result(
            str(new_directory) + "\n"
        )

    except Exception as exc:
        return _error(
            "cd",
            str(exc),
        )


def builtin_ls(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    path = "."

    show_hidden = False

    recursive = False

    for arg in args:

        if arg in (
            "-a",
            "--all",
        ):
            show_hidden = True

        elif arg in (
            "-r",
            "--recursive",
        ):
            recursive = True

        elif not arg.startswith("-"):
            path = arg

    target = _resolve_path(
        path,
        kwargs,
    )

    try:

        entries = list_directory(
            target,
            show_hidden=show_hidden,
            recursive=recursive,
        )

        lines: list[str] = []

        for entry in entries:

            name = getattr(
                entry,
                "name",
                None,
            )

            if name is None:
                lines.append(str(entry))
                continue

            is_directory = getattr(
                entry,
                "is_directory",
                False,
            )

            if callable(is_directory):
                try:
                    is_directory = is_directory()
                except Exception:
                    is_directory = False

            if is_directory:
                name += "/"

            lines.append(name)

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    except Exception as exc:
        return _error(
            "ls",
            str(exc),
        )


# ============================================================================
# FILE READING
# ============================================================================

def builtin_cat(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "cat",
            "missing file",
        )

    output: list[str] = []

    try:

        for path in args:

            target = _resolve_path(
                path,
                kwargs,
            )

            output.append(
                read_file(target)
            )

        return _result(
            "".join(output)
        )

    except Exception as exc:
        return _error(
            "cat",
            str(exc),
        )


builtin_read = builtin_cat


# ============================================================================
# FILE CREATION
# ============================================================================

def builtin_touch(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "touch",
            "missing file",
        )

    try:

        for path in args:

            touch_file(
                _resolve_path(
                    path,
                    kwargs,
                )
            )

        return _result()

    except Exception as exc:
        return _error(
            "touch",
            str(exc),
        )


def builtin_mkdir(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "mkdir",
            "missing directory",
        )

    try:

        for path in args:

            make_directory(
                _resolve_path(
                    path,
                    kwargs,
                ),
                parents=True,
            )

        return _result()

    except Exception as exc:
        return _error(
            "mkdir",
            str(exc),
        )


# ============================================================================
# FILE WRITING
# ============================================================================

def builtin_write(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:
        return _error(
            "write",
            "usage: write <file> <text>",
        )

    target = _resolve_path(
        args[0],
        kwargs,
    )

    text = " ".join(
        args[1:]
    )

    confirmed = bool(
        kwargs.get(
            "confirmed",
            False,
        )
    )

    source = kwargs.get(
        "source",
        "human",
    )

    try:

        write_file(
            target,
            text,
            source=source,
            confirmed=confirmed,
        )

        return _result()

    except Exception as exc:
        return _error(
            "write",
            str(exc),
        )


def builtin_append(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:
        return _error(
            "append",
            "usage: append <file> <text>",
        )

    target = _resolve_path(
        args[0],
        kwargs,
    )

    text = " ".join(
        args[1:]
    )

    confirmed = bool(
        kwargs.get(
            "confirmed",
            False,
        )
    )

    source = kwargs.get(
        "source",
        "human",
    )

    try:

        append_file(
            target,
            text,
            source=source,
            confirmed=confirmed,
        )

        return _result()

    except Exception as exc:
        return _error(
            "append",
            str(exc),
        )


# ============================================================================
# DELETE
# ============================================================================

def builtin_rm(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "rm",
            "missing path",
        )

    recursive = False

    targets: list[str] = []

    for arg in args:

        if arg in (
            "-r",
            "-R",
            "--recursive",
        ):
            recursive = True

        else:
            targets.append(arg)

    if not targets:
        return _error(
            "rm",
            "missing path",
        )

    confirmed = bool(
        kwargs.get(
            "confirmed",
            False,
        )
    )

    source = kwargs.get(
        "source",
        "human",
    )

    try:

        for path in targets:

            delete_path(
                _resolve_path(
                    path,
                    kwargs,
                ),
                recursive=recursive,
                source=source,
                confirmed=confirmed,
            )

        return _result()

    except Exception as exc:
        return _error(
            "rm",
            str(exc),
        )


builtin_del = builtin_rm


# ============================================================================
# COPY
# ============================================================================

def builtin_cp(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:
        return _error(
            "cp",
            "usage: cp <source> <destination>",
        )

    confirmed = bool(
        kwargs.get(
            "confirmed",
            False,
        )
    )

    source = kwargs.get(
        "source",
        "human",
    )

    try:

        copy_path(
            _resolve_path(
                args[0],
                kwargs,
            ),
            _resolve_path(
                args[1],
                kwargs,
            ),
            source=source,
            confirmed=confirmed,
        )

        return _result()

    except Exception as exc:
        return _error(
            "cp",
            str(exc),
        )


builtin_copy = builtin_cp


# ============================================================================
# MOVE
# ============================================================================

def builtin_mv(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:
        return _error(
            "mv",
            "usage: mv <source> <destination>",
        )

    confirmed = bool(
        kwargs.get(
            "confirmed",
            False,
        )
    )

    source = kwargs.get(
        "source",
        "human",
    )

    try:

        move_path(
            _resolve_path(
                args[0],
                kwargs,
            ),
            _resolve_path(
                args[1],
                kwargs,
            ),
            source=source,
            confirmed=confirmed,
        )

        return _result()

    except Exception as exc:
        return _error(
            "mv",
            str(exc),
        )


builtin_move = builtin_mv


# ============================================================================
# SEARCH
# ============================================================================

def builtin_find(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    path = (
        args[0]
        if args
        else "."
    )

    pattern = (
        args[1]
        if len(args) > 1
        else "*"
    )

    try:

        results = search_files(
            _resolve_path(
                path,
                kwargs,
            ),
            pattern=pattern,
        )

        lines = [
            str(item)
            for item in results
        ]

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    except Exception as exc:
        return _error(
            "find",
            str(exc),
        )


def builtin_grep(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "grep",
            "missing search text",
        )

    text = args[0]

    path = (
        args[1]
        if len(args) > 1
        else "."
    )

    try:

        results = find_text(
            _resolve_path(
                path,
                kwargs,
            ),
            text,
        )

        lines = [
            f"{item[0]}:{item[1]}:{item[2]}"
            for item in results
        ]

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    except Exception as exc:
        return _error(
            "grep",
            str(exc),
        )


# ============================================================================
# FILE INFORMATION
# ============================================================================

def builtin_stat(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "stat",
            "missing path",
        )

    target = _resolve_path(
        args[0],
        kwargs,
    )

    try:

        info = get_file_info(
            target
        )

        lines = [
            f"path: {info.path}",
            f"name: {info.name}",
            f"type: {info.type}",
            f"size: {info.size}",
            f"modified: {info.modified}",
            f"permissions: {info.permissions}",
            f"hidden: {info.hidden}",
        ]

        return _result(
            "\n".join(lines) + "\n"
        )

    except Exception as exc:
        return _error(
            "stat",
            str(exc),
        )


def builtin_exists(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "exists",
            "missing path",
        )

    target = _resolve_path(
        args[0],
        kwargs,
    )

    try:

        return _result(
            (
                "true"
                if exists(target)
                else "false"
            )
            + "\n"
        )

    except Exception as exc:
        return _error(
            "exists",
            str(exc),
        )


# ============================================================================
# ENVIRONMENT
# ============================================================================

def _session_environment(
    session: TerminalSession,
) -> dict[str, str]:

    result: dict[str, str] = {}

    try:

        exported = session.export_environment()

        if isinstance(exported, dict):
            for key, value in exported.items():
                result[str(key)] = str(value)

            return result

    except Exception:
        pass

    return result


def builtin_set(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "set",
            "No terminal session is attached.",
        )

    if not args:

        variables = _session_environment(
            session
        )

        lines = [
            f"{key}={value}"
            for key, value in sorted(
                variables.items()
            )
        ]

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    name = args[0]

    if not name:
        return _error(
            "set",
            "invalid variable name",
        )

    value = (
        " ".join(args[1:])
        if len(args) > 1
        else ""
    )

    try:

        session.set_env(
            name,
            value,
        )

        return _result()

    except Exception as exc:
        return _error(
            "set",
            str(exc),
        )


def builtin_unset(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "unset",
            "No terminal session is attached.",
        )

    if not args:
        return _error(
            "unset",
            "missing variable",
        )

    try:

        session.unset_env(
            args[0]
        )

        return _result()

    except Exception as exc:
        return _error(
            "unset",
            str(exc),
        )


def builtin_env(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "env",
            "No terminal session is attached.",
        )

    variables = _session_environment(
        session
    )

    lines = [
        f"{key}={value}"
        for key, value in sorted(
            variables.items()
        )
    ]

    output = "\n".join(lines)

    if output:
        output += "\n"

    return _result(output)


# ============================================================================
# ALIASES
# ============================================================================

def builtin_alias(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "alias",
            "No terminal session is attached.",
        )

    if not args:

        try:
            aliases = session.list_aliases()

            lines = [
                f"{name}={value}"
                for name, value in sorted(
                    aliases.items()
                )
            ]

            output = "\n".join(lines)

            if output:
                output += "\n"

            return _result(output)

        except Exception as exc:
            return _error(
                "alias",
                str(exc),
            )

    name = args[0]

    if len(args) == 1:

        try:

            value = session.get_alias(
                name
            )

            if value is None:
                return _error(
                    "alias",
                    f"alias not found: {name}",
                )

            return _result(
                f"{name}={value}\n"
            )

        except Exception as exc:
            return _error(
                "alias",
                str(exc),
            )

    value = " ".join(
        args[1:]
    )

    try:

        session.set_alias(
            name,
            value,
        )

        return _result()

    except Exception as exc:
        return _error(
            "alias",
            str(exc),
        )


def builtin_unalias(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "unalias",
            "No terminal session is attached.",
        )

    if not args:
        return _error(
            "unalias",
            "missing alias",
        )

    try:

        removed = session.remove_alias(
            args[0]
        )

        if removed is False:
            return _error(
                "unalias",
                f"alias not found: {args[0]}",
            )

        return _result()

    except Exception as exc:
        return _error(
            "unalias",
            str(exc),
        )


# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

def builtin_jobs(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    try:

        processes = process_manager.list(
            include_finished=False
        )

        lines: list[str] = []

        for process in processes:

            info = process.info()

            lines.append(
                f"[{info.process_id}] "
                f"{info.state.value} "
                f"pid={info.pid} "
                f"{info.command}"
            )

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    except Exception as exc:
        return _error(
            "jobs",
            str(exc),
        )


def builtin_ps(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    include_finished = any(
        arg in (
            "-a",
            "--all",
        )
        for arg in args
    )

    try:

        processes = process_manager.list(
            include_finished=include_finished
        )

        lines: list[str] = []

        for process in processes:

            info = process.info()

            lines.append(
                f"{info.process_id:<6} "
                f"{info.pid:<8} "
                f"{info.state.value:<12} "
                f"{info.command}"
            )

        if not lines:
            return _result()

        header = (
            "ID     PID      STATE        COMMAND\n"
        )

        return _result(
            header
            + "\n".join(lines)
            + "\n"
        )

    except Exception as exc:
        return _error(
            "ps",
            str(exc),
        )


def builtin_kill(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "kill",
            "missing process id",
        )

    force = False

    target = None

    for arg in args:

        if arg in (
            "-9",
            "--force",
        ):
            force = True
            continue

        if target is None:
            target = arg

    if target is None:
        return _error(
            "kill",
            "missing process id",
        )

    try:

        process_id = int(target)

    except ValueError:
        return _error(
            "kill",
            "process id must be an integer",
        )

    try:

        if force:

            success = process_manager.kill(
                process_id
            )

        else:

            success = process_manager.terminate(
                process_id
            )

        if not success:
            return _error(
                "kill",
                f"process not found or already finished: {process_id}",
            )

        return _result()

    except Exception as exc:
        return _error(
            "kill",
            str(exc),
        )


# ============================================================================
# SYSTEM
# ============================================================================

def builtin_whoami(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    try:

        return _result(
            getpass.getuser() + "\n"
        )

    except Exception as exc:
        return _error(
            "whoami",
            str(exc),
        )


def builtin_hostname(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    try:

        return _result(
            platform.node() + "\n"
        )

    except Exception as exc:
        return _error(
            "hostname",
            str(exc),
        )


def builtin_sysinfo(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    lines = [
        f"system: {platform.system()}",
        f"release: {platform.release()}",
        f"version: {platform.version()}",
        f"machine: {platform.machine()}",
        f"processor: {platform.processor()}",
        f"python: {platform.python_version()}",
        f"cwd: {_cwd(kwargs)}",
    ]

    return _result(
        "\n".join(lines) + "\n"
    )


# ============================================================================
# MAPLE
# ============================================================================

def builtin_load_maple(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "load maple",
            "No terminal session is attached.",
        )

    try:

        maple_session_id = kwargs.get(
            "maple_session_id"
        )

        session.load_maple(
            maple_session_id=maple_session_id
        )

        return _result(
            "Maple loaded.\n"
        )

    except Exception as exc:
        return _error(
            "load maple",
            str(exc),
        )


def builtin_kill_maple(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "kill maple",
            "No terminal session is attached.",
        )

    try:

        session.kill_maple()

        return _result(
            "Maple unloaded.\n"
        )

    except Exception as exc:
        return _error(
            "kill maple",
            str(exc),
        )


# ============================================================================
# HISTORY
# ============================================================================

def builtin_history(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "history",
            "No terminal session is attached.",
        )

    limit: Optional[int] = None

    if args:

        try:
            limit = int(args[0])

        except ValueError:
            return _error(
                "history",
                "limit must be an integer",
            )

    try:

        entries = session.get_history(
            limit=limit
        )

        lines: list[str] = []

        for index, entry in enumerate(
            entries,
            start=1,
        ):

            command = getattr(
                entry,
                "command",
                str(entry),
            )

            exit_code = getattr(
                entry,
                "exit_code",
                None,
            )

            if exit_code is None:
                lines.append(
                    f"{index:>4}  {command}"
                )

            else:
                lines.append(
                    f"{index:>4}  "
                    f"{command} "
                    f"[exit={exit_code}]"
                )

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    except Exception as exc:
        return _error(
            "history",
            str(exc),
        )


# ============================================================================
# SIMPLE SHELL COMMANDS
# ============================================================================

def builtin_echo(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return _result(
        " ".join(args) + "\n"
    )


def builtin_clear(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    # ANSI clear-screen sequence.
    return _result(
        "\033[2J\033[H"
    )


def builtin_exit(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return _result(
        "",
        return_code=0,
    )


# ============================================================================
# COMMAND REGISTRY
# ============================================================================

BUILTINS: dict[str, Builtin] = {}


def register_builtin(
    name: str,
    handler: Callable,
    description: str,
) -> None:

    BUILTINS[name] = Builtin(
        name=name,
        handler=handler,
        description=description,
    )


def _register_defaults() -> None:

    register_builtin(
        "help",
        builtin_help,
        "Show Convexity commands",
    )

    register_builtin(
        "pwd",
        builtin_pwd,
        "Show current directory",
    )

    register_builtin(
        "cd",
        builtin_cd,
        "Change session directory",
    )

    register_builtin(
        "ls",
        builtin_ls,
        "List directory",
    )

    register_builtin(
        "cat",
        builtin_cat,
        "Read file",
    )

    register_builtin(
        "read",
        builtin_read,
        "Read file",
    )

    register_builtin(
        "touch",
        builtin_touch,
        "Create file",
    )

    register_builtin(
        "mkdir",
        builtin_mkdir,
        "Create directory",
    )

    register_builtin(
        "write",
        builtin_write,
        "Write file",
    )

    register_builtin(
        "append",
        builtin_append,
        "Append to file",
    )

    register_builtin(
        "rm",
        builtin_rm,
        "Delete file or directory",
    )

    register_builtin(
        "del",
        builtin_del,
        "Delete file or directory",
    )

    register_builtin(
        "cp",
        builtin_cp,
        "Copy file or directory",
    )

    register_builtin(
        "copy",
        builtin_copy,
        "Copy file or directory",
    )

    register_builtin(
        "mv",
        builtin_mv,
        "Move file or directory",
    )

    register_builtin(
        "move",
        builtin_move,
        "Move file or directory",
    )

    register_builtin(
        "find",
        builtin_find,
        "Search files",
    )

    register_builtin(
        "grep",
        builtin_grep,
        "Search file contents",
    )

    register_builtin(
        "stat",
        builtin_stat,
        "Show filesystem information",
    )

    register_builtin(
        "exists",
        builtin_exists,
        "Check path existence",
    )

    register_builtin(
        "set",
        builtin_set,
        "Set or list session variables",
    )

    register_builtin(
        "unset",
        builtin_unset,
        "Remove session variable",
    )

    register_builtin(
        "env",
        builtin_env,
        "Show session environment",
    )

    register_builtin(
        "alias",
        builtin_alias,
        "Create or list aliases",
    )

    register_builtin(
        "unalias",
        builtin_unalias,
        "Remove alias",
    )

    register_builtin(
        "jobs",
        builtin_jobs,
        "Show active processes",
    )

    register_builtin(
        "ps",
        builtin_ps,
        "Show managed processes",
    )

    register_builtin(
        "kill",
        builtin_kill,
        "Terminate managed process",
    )

    register_builtin(
        "whoami",
        builtin_whoami,
        "Show current user",
    )

    register_builtin(
        "hostname",
        builtin_hostname,
        "Show computer hostname",
    )

    register_builtin(
        "sysinfo",
        builtin_sysinfo,
        "Show system information",
    )

    register_builtin(
        "history",
        builtin_history,
        "Show command history",
    )

    register_builtin(
        "echo",
        builtin_echo,
        "Print text",
    )

    register_builtin(
        "clear",
        builtin_clear,
        "Clear terminal",
    )

    register_builtin(
        "exit",
        builtin_exit,
        "Exit Convexity",
    )


_register_defaults()


# ============================================================================
# DISPATCH
# ============================================================================

def get_builtin(
    command: str,
) -> Optional[Builtin]:

    return BUILTINS.get(
        command
    )


def is_builtin(
    command: str,
) -> bool:

    return command in BUILTINS


def list_builtins() -> list[Builtin]:

    return sorted(
        BUILTINS.values(),
        key=lambda item: item.name,
    )


def execute_builtin(
    command: str,
    args: Optional[list[str]] = None,
    *,
    session: Optional[TerminalSession] = None,
    source: str = "human",
    confirmed: bool = False,
    **kwargs,
) -> BuiltinResult:

    builtin = get_builtin(
        command
    )

    if builtin is None:
        return BuiltinResult(
            handled=False
        )

    if args is None:
        args = []

    call_kwargs = dict(kwargs)

    call_kwargs.update(
        {
            "session": session,
            "source": source,
            "confirmed": confirmed,
        }
    )

    try:

        return builtin.handler(
            args,
            **call_kwargs,
        )

    except Exception as exc:

        return _error(
            command,
            str(exc),
        )


# ============================================================================
# ALIASES / COMPATIBILITY
# ============================================================================

builtin_read = builtin_cat
builtin_del = builtin_rm
builtin_copy = builtin_cp
builtin_move = builtin_mv


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "BuiltinResult",
    "Builtin",
    "BUILTINS",
    "register_builtin",
    "get_builtin",
    "is_builtin",
    "list_builtins",
    "execute_builtin",
    "builtin_help",
    "builtin_pwd",
    "builtin_cd",
    "builtin_ls",
    "builtin_cat",
    "builtin_read",
    "builtin_touch",
    "builtin_mkdir",
    "builtin_write",
    "builtin_append",
    "builtin_rm",
    "builtin_del",
    "builtin_cp",
    "builtin_copy",
    "builtin_mv",
    "builtin_move",
    "builtin_find",
    "builtin_grep",
    "builtin_stat",
    "builtin_exists",
    "builtin_set",
    "builtin_unset",
    "builtin_env",
    "builtin_alias",
    "builtin_unalias",
    "builtin_jobs",
    "builtin_ps",
    "builtin_kill",
    "builtin_whoami",
    "builtin_hostname",
    "builtin_sysinfo",
    "builtin_load_maple",
    "builtin_kill_maple",
    "builtin_history",
    "builtin_echo",
    "builtin_clear",
    "builtin_exit",
]

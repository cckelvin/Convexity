"""
Convexity Native Built-ins
Version: 1.1.0

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
import shlex

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
)

from .process import (
    process_manager,
    ProcessState,
)

from .session import TerminalSession


__version__ = "1.1.0"


# ============================================================================
# RESULT TYPES
# ============================================================================

@dataclass
class BuiltinResult:
    """Result returned by a native Convexity built-in."""

    handled: bool

    success: bool = True

    stdout: str = ""

    stderr: str = ""

    return_code: int = 0


@dataclass
class Builtin:
    """Registered Convexity built-in command."""

    name: str

    handler: Callable

    description: str


# ============================================================================
# HELPERS
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
    Resolve a path against the Convexity session cwd.

    This never calls os.chdir().
    """

    path = os.path.expandvars(
        os.path.expanduser(path)
    )

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


def _require_session(kwargs) -> Optional[BuiltinResult]:
    if _get_session(kwargs) is None:
        return _error(
            "convexity",
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
        "  jobs                    Show background jobs",
        "  ps                      Show Convexity processes",
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

            content = read_file(
                target
            )

            output.append(
                str(content)
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

    try:
        write_file(
            target,
            text,
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

    try:
        append_file(
            target,
            text,
        )

        return _result()

    except Exception as exc:
        return _error(
            "append",
            str(exc),
        )


# ============================================================================
# FILE DELETE
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

    try:
        for path in targets:

            delete_path(
                _resolve_path(
                    path,
                    kwargs,
                ),
                recursive=recursive,
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
# COPY / MOVE
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
        )

        return _result()

    except Exception as exc:
        return _error(
            "cp",
            str(exc),
        )


builtin_copy = builtin_cp


def builtin_mv(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if len(args) < 2:
        return _error(
            "mv",
            "usage: mv <source> <destination>",
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

    path = "."

    pattern = "*"

    if args:
        path = args[0]

    if len(args) > 1:
        pattern = args[1]

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
            str(item)
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
# ENVIRONMENT
# ============================================================================

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

        lines = [
            f"{key}={value}"
            for key, value in sorted(
                session.environment.items()
            )
        ]

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    name = args[0]

    if len(args) > 1:
        value = " ".join(
            args[1:]
        )
    else:
        value = ""

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

    lines = [
        f"{key}={value}"
        for key, value in sorted(
            session.environment.items()
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

        aliases = session.list_aliases()

        lines = [
            f"alias {name}='{command}'"
            for name, command in sorted(
                aliases.items()
            )
        ]

        output = "\n".join(lines)

        if output:
            output += "\n"

        return _result(output)

    name = args[0]

    if len(args) == 1:

        command = session.get_alias(
            name
        )

        if command is None:
            return _error(
                "alias",
                f"alias not found: {name}",
            )

        return _result(
            f"alias {name}='{command}'\n"
        )

    command = " ".join(
        args[1:]
    )

    try:
        session.set_alias(
            name,
            command,
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

        if not removed:
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

    limit = None

    if args:
        try:
            limit = int(
                args[0]
            )
        except ValueError:
            return _error(
                "history",
                "invalid number",
            )

    entries = session.get_history(
        limit=limit
    )

    lines: list[str] = []

    for index, entry in enumerate(
        entries,
        start=1,
    ):
        lines.append(
            f"{index:>4}  {entry.command}"
        )

    output = "\n".join(lines)

    if output:
        output += "\n"

    return _result(output)


# ============================================================================
# PROCESS / JOBS
# ============================================================================

def _process_state_name(
    process,
) -> str:

    try:
        state = process.state

        if isinstance(
            state,
            ProcessState,
        ):
            return state.value

        return str(state)

    except Exception:
        return "unknown"


def builtin_jobs(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    try:
        jobs = process_manager.list(
            include_finished=False
        )

        lines: list[str] = []

        for process in jobs:

            process_id = getattr(
                process,
                "process_id",
                getattr(
                    process,
                    "id",
                    "?",
                ),
            )

            pid = getattr(
                process,
                "pid",
                "?",
            )

            state = _process_state_name(
                process
            )

            lines.append(
                f"[{process_id}] "
                f"PID={pid} "
                f"{state}"
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

    try:
        processes = process_manager.list(
            include_finished=False
        )

        lines = [
            "ID\tPID\tSTATE\tCOMMAND"
        ]

        for process in processes:

            process_id = getattr(
                process,
                "process_id",
                getattr(
                    process,
                    "id",
                    "?",
                ),
            )

            pid = getattr(
                process,
                "pid",
                "?",
            )

            state = _process_state_name(
                process
            )

            command = getattr(
                process,
                "command",
                "",
            )

            if isinstance(
                command,
                (list, tuple),
            ):
                command = " ".join(
                    str(item)
                    for item in command
                )

            lines.append(
                f"{process_id}\t"
                f"{pid}\t"
                f"{state}\t"
                f"{command}"
            )

        return _result(
            "\n".join(lines) + "\n"
        )

    except Exception as exc:
        return _error(
            "ps",
            str(exc),
        )


def _find_process(identifier: str):
    try:
        number = int(identifier)
    except ValueError:
        number = None

    if number is not None:

        try:
            process = process_manager.get(
                number
            )

            if process is not None:
                return process

        except Exception:
            pass

    try:
        processes = process_manager.list(
            include_finished=True
        )

        for process in processes:

            process_id = getattr(
                process,
                "process_id",
                None,
            )

            pid = getattr(
                process,
                "pid",
                None,
            )

            if str(process_id) == identifier:
                return process

            if str(pid) == identifier:
                return process

    except Exception:
        pass

    return None


def builtin_kill(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        return _error(
            "kill",
            "usage: kill [-9] <process-id-or-pid>",
        )

    force = False

    identifiers: list[str] = []

    for arg in args:

        if arg in (
            "-9",
            "--force",
        ):
            force = True
        else:
            identifiers.append(arg)

    if not identifiers:
        return _error(
            "kill",
            "missing process ID",
        )

    identifier = identifiers[0]

    if identifier.lower() == "maple":
        return builtin_kill_maple(
            [],
            **kwargs,
        )

    process = _find_process(
        identifier
    )

    if process is None:
        return _error(
            "kill",
            f"process not found: {identifier}",
        )

    try:

        process_id = getattr(
            process,
            "process_id",
            identifier,
        )

        if force:
            process_manager.kill(
                process_id
            )
        else:
            process_manager.terminate(
                process_id
            )

        return _result()

    except Exception as exc:
        return _error(
            "kill",
            str(exc),
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
            "load",
            "No terminal session is attached.",
        )

    session.load_maple()

    return _result(
        "Maple loaded.\n"
    )


def builtin_kill_maple(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    session = _get_session(kwargs)

    if session is None:
        return _error(
            "kill",
            "No terminal session is attached.",
        )

    session.kill_maple()

    return _result(
        "Maple unloaded.\n"
    )


def builtin_maple(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    if not args:
        session = _get_session(kwargs)

        if session is not None and session.is_maple_loaded():
            return _result(
                "Maple is loaded.\n"
            )

        return _result(
            "Maple is not loaded.\n"
        )

    action = args[0].lower()

    if action in (
        "load",
        "start",
        "on",
    ):
        return builtin_load_maple(
            args[1:],
            **kwargs,
        )

    if action in (
        "kill",
        "stop",
        "off",
        "unload",
    ):
        return builtin_kill_maple(
            args[1:],
            **kwargs,
        )

    return _error(
        "maple",
        "usage: maple [load|kill]",
    )


# ============================================================================
# SYSTEM INFORMATION
# ============================================================================

def builtin_whoami(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    try:
        return _result(
            getpass.getuser() + "\n"
        )
    except Exception:
        return _result(
            os.environ.get(
                "USERNAME",
                os.environ.get(
                    "USER",
                    "unknown",
                ),
            )
            + "\n"
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

    session = _get_session(kwargs)

    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "os_name": os.name,
        "cwd": (
            session.cwd
            if session is not None
            else os.getcwd()
        ),
        "maple_loaded": (
            session.is_maple_loaded()
            if session is not None
            else False
        ),
    }

    lines = [
        f"{key}: {value}"
        for key, value in info.items()
    ]

    return _result(
        "\n".join(lines) + "\n"
    )


# ============================================================================
# OUTPUT / TERMINAL
# ============================================================================

def builtin_echo(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    text = " ".join(args)

    session = _get_session(kwargs)

    if session is not None:
        text = os.path.expandvars(
            text
        )

    return _result(
        text + "\n"
    )


def builtin_clear(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return _result(
        "\033[2J\033[H"
    )


def builtin_exit(
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    return _result(
        "exit\n"
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
        stat = os.stat(target)

        lines = [
            f"path: {target}",
            f"size: {stat.st_size}",
            f"mode: {oct(stat.st_mode)}",
            f"modified: {stat.st_mtime}",
            f"directory: {os.path.isdir(target)}",
            f"file: {os.path.isfile(target)}",
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

    return _result(
        (
            "true"
            if os.path.exists(target)
            else "false"
        )
        + "\n"
    )


# ============================================================================
# COMMAND REGISTRY
# ============================================================================

BUILTINS: dict[str, Builtin] = {
    # Navigation
    "cd": Builtin(
        "cd",
        builtin_cd,
        "Change session directory",
    ),
    "pwd": Builtin(
        "pwd",
        builtin_pwd,
        "Show current directory",
    ),
    "ls": Builtin(
        "ls",
        builtin_ls,
        "List directory",
    ),
    "dir": Builtin(
        "dir",
        builtin_ls,
        "List directory",
    ),

    # Files
    "cat": Builtin(
        "cat",
        builtin_cat,
        "Read file",
    ),
    "read": Builtin(
        "read",
        builtin_read,
        "Read file",
    ),
    "touch": Builtin(
        "touch",
        builtin_touch,
        "Create file",
    ),
    "mkdir": Builtin(
        "mkdir",
        builtin_mkdir,
        "Create directory",
    ),
    "write": Builtin(
        "write",
        builtin_write,
        "Write file",
    ),
    "append": Builtin(
        "append",
        builtin_append,
        "Append to file",
    ),
    "rm": Builtin(
        "rm",
        builtin_rm,
        "Delete path",
    ),
    "del": Builtin(
        "del",
        builtin_del,
        "Delete path",
    ),
    "cp": Builtin(
        "cp",
        builtin_cp,
        "Copy path",
    ),
    "copy": Builtin(
        "copy",
        builtin_copy,
        "Copy path",
    ),
    "mv": Builtin(
        "mv",
        builtin_mv,
        "Move path",
    ),
    "move": Builtin(
        "move",
        builtin_move,
        "Move path",
    ),

    # Search
    "find": Builtin(
        "find",
        builtin_find,
        "Search files",
    ),
    "grep": Builtin(
        "grep",
        builtin_grep,
        "Search file contents",
    ),

    # Environment
    "set": Builtin(
        "set",
        builtin_set,
        "Set/list variables",
    ),
    "unset": Builtin(
        "unset",
        builtin_unset,
        "Remove variable",
    ),
    "env": Builtin(
        "env",
        builtin_env,
        "Show environment",
    ),

    # Aliases
    "alias": Builtin(
        "alias",
        builtin_alias,
        "Create/list aliases",
    ),
    "unalias": Builtin(
        "unalias",
        builtin_unalias,
        "Remove alias",
    ),

    # History
    "history": Builtin(
        "history",
        builtin_history,
        "Show command history",
    ),

    # Processes
    "jobs": Builtin(
        "jobs",
        builtin_jobs,
        "Show jobs",
    ),
    "ps": Builtin(
        "ps",
        builtin_ps,
        "Show processes",
    ),
    "kill": Builtin(
        "kill",
        builtin_kill,
        "Terminate process",
    ),

    # Maple
    "maple": Builtin(
        "maple",
        builtin_maple,
        "Control Maple",
    ),

    # System
    "whoami": Builtin(
        "whoami",
        builtin_whoami,
        "Show current user",
    ),
    "hostname": Builtin(
        "hostname",
        builtin_hostname,
        "Show computer name",
    ),
    "sysinfo": Builtin(
        "sysinfo",
        builtin_sysinfo,
        "Show system information",
    ),

    # Terminal
    "echo": Builtin(
        "echo",
        builtin_echo,
        "Print text",
    ),
    "clear": Builtin(
        "clear",
        builtin_clear,
        "Clear terminal",
    ),
    "exit": Builtin(
        "exit",
        builtin_exit,
        "Exit terminal",
    ),

    # File information
    "stat": Builtin(
        "stat",
        builtin_stat,
        "Show file information",
    ),
    "exists": Builtin(
        "exists",
        builtin_exists,
        "Check whether path exists",
    ),

    # Help
    "help": Builtin(
        "help",
        builtin_help,
        "Show Convexity commands",
    ),
}


# ============================================================================
# COMMAND LOOKUP
# ============================================================================

def get_builtin(
    name: str,
) -> Optional[Builtin]:

    return BUILTINS.get(
        name.lower()
    )


def is_builtin(
    name: str,
) -> bool:

    return name.lower() in BUILTINS


def list_builtins() -> list[Builtin]:

    return sorted(
        BUILTINS.values(),
        key=lambda item: item.name,
    )


# ============================================================================
# BUILTIN EXECUTION
# ============================================================================

def execute_builtin(
    command: str,
    *,
    session: Optional[TerminalSession] = None,
    confirmed: bool = False,
    **kwargs,
) -> BuiltinResult:

    if not command or not command.strip():
        return BuiltinResult(
            handled=False
        )

    try:
        tokens = shlex.split(
            command
        )
    except ValueError as exc:
        return _error(
            "builtin",
            f"parse error: {exc}",
        )

    if not tokens:
        return BuiltinResult(
            handled=False
        )

    name = tokens[0].lower()

    builtin = get_builtin(
        name
    )

    if builtin is None:
        return BuiltinResult(
            handled=False
        )

    execution_kwargs = dict(
        kwargs
    )

    execution_kwargs["session"] = session
    execution_kwargs["confirmed"] = confirmed

    try:
        return builtin.handler(
            tokens[1:],
            **execution_kwargs,
        )

    except Exception as exc:
        return _error(
            name,
            str(exc),
        )


# ============================================================================
# ALIASES / COMMAND NORMALIZATION
# ============================================================================

def expand_builtin_alias(
    command: str,
    session: Optional[TerminalSession],
) -> str:

    if session is None:
        return command

    try:
        return session.expand_alias(
            command
        )
    except Exception:
        return command


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BuiltinResult",
    "Builtin",
    "BUILTINS",
    "get_builtin",
    "is_builtin",
    "list_builtins",
    "execute_builtin",
    "expand_builtin_alias",

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

    "builtin_set",
    "builtin_unset",
    "builtin_env",

    "builtin_alias",
    "builtin_unalias",
    "builtin_history",

    "builtin_jobs",
    "builtin_ps",
    "builtin_kill",

    "builtin_maple",
    "builtin_load_maple",
    "builtin_kill_maple",

    "builtin_whoami",
    "builtin_hostname",
    "builtin_sysinfo",

    "builtin_echo",
    "builtin_clear",
    "builtin_exit",

    "builtin_stat",
    "builtin_exists",
]

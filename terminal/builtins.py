"""
Convexity Native Built-ins
Version 1.0.0

Native commands provided directly by Convexity.

These commands do not depend on Bash, PowerShell, CMD, or Termux.
They operate through Convexity's session, filesystem, and process layers.
"""

from __future__ import annotations

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

from .environment import (
    set_variable,
    get_variable,
    unset_variable,
    expand_variables,
    set_alias,
    get_alias,
    remove_alias,
    context,
)

from .process import (
    process_manager,
    ProcessState,
)

from .job import (
    job_manager,
)

from .session import TerminalSession


# ============================================================================
# RESULT
# ============================================================================

@dataclass
class BuiltinResult:
    handled: bool
    success: bool = True
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


@dataclass
class Builtin:
    name: str
    handler: Callable
    description: str


# ============================================================================
# HELP
# ============================================================================

def builtin_help(args: list[str], **kwargs) -> BuiltinResult:
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
        "  mkdir <path>           Create directory",
        "  rm <path>              Delete file/directory",
        "  cp <source> <dest>     Copy",
        "  mv <source> <dest>     Move",
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
        "  jobs                    Show jobs",
        "  ps                      Show processes",
        "  kill <pid>              Terminate process",
        "  kill -9 <pid>           Force kill",
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

    return BuiltinResult(
        handled=True,
        stdout="\n".join(lines) + "\n",
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


def _resolve_path(path: str, kwargs) -> str:
    """
    Resolve a path relative to the Convexity session.

    Does not change the process-wide working directory.
    """

    path = expand_variables(path)

    session = _get_session(kwargs)

    if session is not None:
        if os.path.isabs(path):
            return os.path.normpath(path)

        return os.path.normpath(
            os.path.join(session.cwd, path)
        )

    return os.path.abspath(path)


# ============================================================================
# NAVIGATION
# ============================================================================

def builtin_pwd(args: list[str], **kwargs) -> BuiltinResult:
    return BuiltinResult(
        handled=True,
        stdout=_cwd(kwargs) + "\n",
    )


def builtin_cd(args: list[str], **kwargs) -> BuiltinResult:
    session = _get_session(kwargs)

    path = args[0] if args else os.path.expanduser("~")

    target = _resolve_path(path, kwargs)

    if not os.path.isdir(target):
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"cd: not a directory: {path}\n",
            return_code=1,
        )

    if session is not None:
        session.cwd = target
    else:
        # Fallback only when no Convexity session exists.
        os.chdir(target)

    return BuiltinResult(
        handled=True,
        stdout=target + "\n",
    )


def builtin_ls(args: list[str], **kwargs) -> BuiltinResult:
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

    target = _resolve_path(path, kwargs)

    try:
        entries = list_directory(
            target,
            show_hidden=show_hidden,
            recursive=recursive,
        )

        lines = []

        for entry in entries:
            if hasattr(entry, "name"):
                name = entry.name

                if getattr(entry, "is_directory", False):
                    name += "/"

                lines.append(name)
            else:
                lines.append(str(entry))

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"ls: {exc}\n",
            return_code=1,
        )


# ============================================================================
# FILE COMMANDS
# ============================================================================

def builtin_cat(args: list[str], **kwargs) -> BuiltinResult:
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
            target = _resolve_path(path, kwargs)
            output.append(read_file(target))

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


def builtin_touch(args: list[str], **kwargs) -> BuiltinResult:
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
                _resolve_path(path, kwargs)
            )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"touch: {exc}\n",
            return_code=1,
        )


def builtin_mkdir(args: list[str], **kwargs) -> BuiltinResult:
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
                _resolve_path(path, kwargs),
                parents=True,
            )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"mkdir: {exc}\n",
            return_code=1,
        )


def builtin_write(args: list[str], **kwargs) -> BuiltinResult:
    if len(args) < 2:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="write: usage: write <file> <text>\n",
            return_code=1,
        )

    target = _resolve_path(args[0], kwargs)
    text = " ".join(args[1:])

    try:
        write_file(
            target,
            text,
        )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"write: {exc}\n",
            return_code=1,
        )


def builtin_append(args: list[str], **kwargs) -> BuiltinResult:
    if len(args) < 2:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="append: usage: append <file> <text>\n",
            return_code=1,
        )

    target = _resolve_path(args[0], kwargs)
    text = " ".join(args[1:])

    try:
        append_file(
            target,
            text,
        )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"append: {exc}\n",
            return_code=1,
        )


def builtin_rm(args: list[str], **kwargs) -> BuiltinResult:
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
                _resolve_path(path, kwargs),
                recursive=recursive,
                confirmed=kwargs.get("confirmed", False),
            )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"rm: {exc}\n",
            return_code=1,
        )


def builtin_cp(args: list[str], **kwargs) -> BuiltinResult:
    if len(args) < 2:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="cp: usage: cp <source> <destination>\n",
            return_code=1,
        )

    try:
        copy_path(
            _resolve_path(args[0], kwargs),
            _resolve_path(args[1], kwargs),
        )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"cp: {exc}\n",
            return_code=1,
        )


def builtin_mv(args: list[str], **kwargs) -> BuiltinResult:
    if len(args) < 2:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="mv: usage: mv <source> <destination>\n",
            return_code=1,
        )

    try:
        move_path(
            _resolve_path(args[0], kwargs),
            _resolve_path(args[1], kwargs),
        )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"mv: {exc}\n",
            return_code=1,
        )


# ============================================================================
# SEARCH
# ============================================================================

def builtin_find(args: list[str], **kwargs) -> BuiltinResult:
    path = args[0] if args else "."
    pattern = args[1] if len(args) > 1 else "*"

    try:
        results = search_files(
            _resolve_path(path, kwargs),
            pattern=pattern,
        )

        lines = [str(item) for item in results]

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"find: {exc}\n",
            return_code=1,
        )


def builtin_grep(args: list[str], **kwargs) -> BuiltinResult:
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
            _resolve_path(path, kwargs),
            text,
        )

        lines = [str(item) for item in results]

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"grep: {exc}\n",
            return_code=1,
        )


# ============================================================================
# ENVIRONMENT
# ============================================================================

def builtin_set(args: list[str], **kwargs) -> BuiltinResult:
    if not args:
        variables = context.environment.list_variables()

        lines = [
            f"{key}={value}"
            for key, value in variables.items()
        ]

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
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

    return BuiltinResult(handled=True)


def builtin_unset(args: list[str], **kwargs) -> BuiltinResult:
    if not args:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="unset: missing variable\n",
            return_code=1,
        )

    result = unset_variable(args[0])

    if not result.success:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(handled=True)


def builtin_env(args: list[str], **kwargs) -> BuiltinResult:
    variables = context.environment.list_variables()

    lines = [
        f"{key}={value}"
        for key, value in variables.items()
    ]

    return BuiltinResult(
        handled=True,
        stdout=(
            "\n".join(lines)
            + ("\n" if lines else "")
        ),
    )


# ============================================================================
# ALIASES
# ============================================================================

def builtin_alias(args: list[str], **kwargs) -> BuiltinResult:
    if not args:
        aliases = context.environment.list_aliases()

        lines = [
            f"{name}={command}"
            for name, command in aliases.items()
        ]

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
        )

    if len(args) < 2:
        existing = get_alias(args[0])

        if existing is None:
            return BuiltinResult(
                handled=True,
                success=False,
                stderr=f"alias: not found: {args[0]}\n",
                return_code=1,
            )

        return BuiltinResult(
            handled=True,
            stdout=f"{args[0]}={existing}\n",
        )

    name = args[0]
    command = " ".join(args[1:])

    result = set_alias(
        name,
        command,
    )

    if not result.success:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(handled=True)


def builtin_unalias(args: list[str], **kwargs) -> BuiltinResult:
    if not args:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="unalias: missing name\n",
            return_code=1,
        )

    result = remove_alias(args[0])

    if not result.success:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=result.error + "\n",
            return_code=1,
        )

    return BuiltinResult(handled=True)
# ============================================================================
# PROCESS / JOB COMMANDS
# ============================================================================

def builtin_jobs(args: list[str], **kwargs) -> BuiltinResult:
    try:
        jobs = job_manager.list_jobs(
            include_finished=False
        )

        if not jobs:
            return BuiltinResult(
                handled=True,
                stdout="No active jobs.\n",
            )

        lines = [
            "JOB ID       PID        STATE        COMMAND"
        ]

        for job in jobs:
            process = getattr(job, "process", None)

            pid = getattr(
                process,
                "pid",
                getattr(job, "pid", "?"),
            )

            state = getattr(
                process,
                "state",
                getattr(job, "state", "?"),
            )

            command = getattr(
                process,
                "command",
                getattr(job, "command", ""),
            )

            if isinstance(command, (list, tuple)):
                command = " ".join(
                    str(item) for item in command
                )

            lines.append(
                f"{getattr(job, 'id', '?'):<12}"
                f"{str(pid):<11}"
                f"{str(state):<13}"
                f"{command}"
            )

        return BuiltinResult(
            handled=True,
            stdout="\n".join(lines) + "\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"jobs: {exc}\n",
            return_code=1,
        )


def builtin_ps(args: list[str], **kwargs) -> BuiltinResult:
    try:
        processes = process_manager.list(
            include_finished=False
        )

        if not processes:
            return BuiltinResult(
                handled=True,
                stdout="No active processes.\n",
            )

        lines = [
            "ID                         PID        STATE        COMMAND"
        ]

        for info in processes:
            process_id = getattr(
                info,
                "id",
                getattr(info, "process_id", "?"),
            )

            pid = getattr(
                info,
                "pid",
                "?",
            )

            state = getattr(
                info,
                "state",
                "?",
            )

            command = getattr(
                info,
                "command",
                "",
            )

            if isinstance(command, (list, tuple)):
                command = " ".join(
                    str(item) for item in command
                )

            lines.append(
                f"{str(process_id):<27}"
                f"{str(pid):<11}"
                f"{str(state):<13}"
                f"{command}"
            )

        return BuiltinResult(
            handled=True,
            stdout="\n".join(lines) + "\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"ps: {exc}\n",
            return_code=1,
        )


def _find_process(identifier: str):
    """
    Resolve either a Convexity process ID or an OS PID.
    """

    process = process_manager.get(identifier)

    if process is not None:
        return process

    try:
        pid = int(identifier)
    except ValueError:
        return None

    for info in process_manager.list(
        include_finished=True
    ):
        if getattr(info, "pid", None) == pid:
            process_id = getattr(
                info,
                "id",
                getattr(info, "process_id", None),
            )

            if process_id is not None:
                return process_manager.get(process_id)

    return None


def builtin_kill(args: list[str], **kwargs) -> BuiltinResult:
    if not args:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="kill: missing process ID\n",
            return_code=1,
        )

    force = False
    identifier = None

    for arg in args:
        if arg in ("-9", "--force"):
            force = True
        elif identifier is None:
            identifier = arg

    if identifier is None:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="kill: missing process ID\n",
            return_code=1,
        )

    process = _find_process(identifier)

    if process is None:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"kill: process not found: {identifier}\n",
            return_code=1,
        )

    try:
        if force:
            process_manager.kill(
                getattr(
                    process,
                    "id",
                    identifier,
                )
            )
        else:
            process_manager.terminate(
                getattr(
                    process,
                    "id",
                    identifier,
                )
            )

        return BuiltinResult(handled=True)

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"kill: {exc}\n",
            return_code=1,
        )


# ============================================================================
# SYSTEM INFORMATION
# ============================================================================

def builtin_whoami(args: list[str], **kwargs) -> BuiltinResult:
    try:
        import getpass

        return BuiltinResult(
            handled=True,
            stdout=getpass.getuser() + "\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"whoami: {exc}\n",
            return_code=1,
        )


def builtin_hostname(args: list[str], **kwargs) -> BuiltinResult:
    try:
        return BuiltinResult(
            handled=True,
            stdout=platform.node() + "\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"hostname: {exc}\n",
            return_code=1,
        )


def builtin_sysinfo(args: list[str], **kwargs) -> BuiltinResult:
    lines = [
        f"System:       {platform.system()}",
        f"Release:      {platform.release()}",
        f"Version:      {platform.version()}",
        f"Machine:      {platform.machine()}",
        f"Architecture: {platform.architecture()[0]}",
        f"Processor:    {platform.processor()}",
        f"Python:       {platform.python_version()}",
        f"Directory:    {_cwd(kwargs)}",
    ]

    return BuiltinResult(
        handled=True,
        stdout="\n".join(lines) + "\n",
    )


# ============================================================================
# SHELL UTILITIES
# ============================================================================

def builtin_echo(args: list[str], **kwargs) -> BuiltinResult:
    return BuiltinResult(
        handled=True,
        stdout=" ".join(args) + "\n",
    )


def builtin_clear(args: list[str], **kwargs) -> BuiltinResult:
    return BuiltinResult(
        handled=True,
        stdout="\033[2J\033[H",
    )


def builtin_history(args: list[str], **kwargs) -> BuiltinResult:
    session = _get_session(kwargs)

    if session is None:
        return BuiltinResult(
            handled=True,
            stderr="history: no active session\n",
            success=False,
            return_code=1,
        )

    try:
        entries = session.get_history()

        lines = []

        for index, entry in enumerate(entries, start=1):
            command = getattr(
                entry,
                "command",
                str(entry),
            )

            lines.append(
                f"{index:>5}  {command}"
            )

        return BuiltinResult(
            handled=True,
            stdout=(
                "\n".join(lines)
                + ("\n" if lines else "")
            ),
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"history: {exc}\n",
            return_code=1,
        )


# ============================================================================
# MAPLE CONTROL
# ============================================================================

def builtin_load_maple(args: list[str], **kwargs) -> BuiltinResult:
    session = _get_session(kwargs)

    if session is None:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="load maple: no active terminal session\n",
            return_code=1,
        )

    try:
        session.load_maple()

        return BuiltinResult(
            handled=True,
            stdout="Maple activated for this terminal session.\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"load maple: {exc}\n",
            return_code=1,
        )


def builtin_kill_maple(args: list[str], **kwargs) -> BuiltinResult:
    session = _get_session(kwargs)

    if session is None:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr="kill maple: no active terminal session\n",
            return_code=1,
        )

    try:
        session.kill_maple()

        return BuiltinResult(
            handled=True,
            stdout="Maple deactivated for this terminal session.\n",
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"kill maple: {exc}\n",
            return_code=1,
        )


# ============================================================================
# BUILTIN REGISTRY
# ============================================================================

BUILTINS: dict[str, Builtin] = {
    "help": Builtin(
        "help",
        builtin_help,
        "Show Convexity commands",
    ),

    "pwd": Builtin(
        "pwd",
        builtin_pwd,
        "Show current directory",
    ),

    "cd": Builtin(
        "cd",
        builtin_cd,
        "Change directory",
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

    "cat": Builtin(
        "cat",
        builtin_cat,
        "Read file",
    ),

    "read": Builtin(
        "read",
        builtin_cat,
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
        "Delete file/directory",
    ),

    "del": Builtin(
        "del",
        builtin_rm,
        "Delete file/directory",
    ),

    "cp": Builtin(
        "cp",
        builtin_cp,
        "Copy file/directory",
    ),

    "copy": Builtin(
        "copy",
        builtin_cp,
        "Copy file/directory",
    ),

    "mv": Builtin(
        "mv",
        builtin_mv,
        "Move file/directory",
    ),

    "move": Builtin(
        "move",
        builtin_mv,
        "Move file/directory",
    ),

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

    "jobs": Builtin(
        "jobs",
        builtin_jobs,
        "Show background jobs",
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

    "history": Builtin(
        "history",
        builtin_history,
        "Show command history",
    ),

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

    "load": Builtin(
        "load",
        builtin_load_maple,
        "Activate Maple",
    ),

    "killmaple": Builtin(
        "killmaple",
        builtin_kill_maple,
        "Deactivate Maple",
    ),
}


# ============================================================================
# DISPATCH
# ============================================================================

def execute_builtin(
    name: str,
    args: list[str],
    **kwargs,
) -> BuiltinResult:

    builtin = BUILTINS.get(
        name.lower()
    )

    if builtin is None:
        return BuiltinResult(
            handled=False
        )

    try:
        return builtin.handler(
            args,
            **kwargs,
        )

    except Exception as exc:
        return BuiltinResult(
            handled=True,
            success=False,
            stderr=f"{name}: {exc}\n",
            return_code=1,
        )


def is_builtin(name: str) -> bool:
    return name.lower() in BUILTINS


def get_builtin(name: str) -> Optional[Builtin]:
    return BUILTINS.get(name.lower())


def list_builtins() -> list[Builtin]:
    return list(BUILTINS.values())
"""
Convexity Security and Permission Layer
Version 1.0.0

Responsibilities:
- Validate filesystem paths
- Detect potentially dangerous commands
- Analyze shell syntax
- Provide Maple permission checks
- Validate structured Maple actions
- Filter child-process environments
- Enforce optional sandbox boundaries

Important:
    Convexity does NOT use this module to restrict normal human terminal use.

    Manual terminal commands are allowed normally.

    When Maple is the execution source, dangerous operations require
    explicit confirmation.

This module never executes commands.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .config import config


# ============================================================================
# EXCEPTIONS
# ============================================================================


class SecurityError(Exception):
    """Base exception for Convexity security errors."""


class PermissionDenied(SecurityError):
    """Raised when an operation requires permission but was not confirmed."""


# ============================================================================
# COMMAND ANALYSIS
# ============================================================================


@dataclass
class CommandAnalysis:
    """Result of analyzing a command without executing it."""

    command: str
    executable: str
    arguments: List[str]

    dangerous: bool = False
    requires_confirmation: bool = False

    contains_shell_operator: bool = False
    shell_operator: Optional[str] = None

    reason: str = ""

    source: str = "human"

    @property
    def allowed(self) -> bool:
        """
        Whether the command is currently allowed to proceed.

        A dangerous Maple command is not considered allowed until the caller
        supplies confirmation.

        Human commands are not blocked merely because they are dangerous.
        """

        if self.source.lower() == "maple":
            return not self.requires_confirmation

        return True


# ============================================================================
# PATH SECURITY
# ============================================================================


def _path_within(parent: Path, child: Path) -> bool:
    """Return True when child is inside parent."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_path(
    path: str | Path,
    *,
    must_exist: bool = False,
    allow_missing: bool = True,
) -> Path:
    """
    Resolve and validate a filesystem path.

    Relative paths are resolved against the current process working
    directory. Session-specific cwd handling belongs to session.py/runtime.py.

    If SANDBOX_ENABLED is enabled, the final path must remain inside the
    configured sandbox.
    """

    if path is None:
        raise SecurityError("Path cannot be None.")

    path_obj = Path(path).expanduser()

    if not str(path_obj).strip():
        raise SecurityError("Path cannot be empty.")

    try:
        if path_obj.exists():
            resolved = path_obj.resolve(strict=True)
        else:
            if not allow_missing:
                raise SecurityError(
                    f"Path does not exist: {path_obj}"
                )

            # Resolve as much of the path as possible while allowing the
            # final target to not exist yet.
            resolved = path_obj.resolve(strict=False)

    except OSError as exc:
        raise SecurityError(
            f"Unable to resolve path: {path_obj}"
        ) from exc

    if len(str(resolved)) > config.MAX_PATH_LENGTH:
        raise SecurityError(
            "Path exceeds Convexity's maximum path length."
        )

    if must_exist and not resolved.exists():
        raise SecurityError(
            f"Path does not exist: {resolved}"
        )

    if config.SANDBOX_ENABLED:
        sandbox_root = Path(
            config.get_sandbox_root()
        ).expanduser().resolve()

        if not _path_within(sandbox_root, resolved):
            raise SecurityError(
                "Access outside the Convexity sandbox is blocked:\n"
                f"{resolved}"
            )

    return resolved


def validate_directory(path: str | Path) -> Path:
    """Validate that a path exists and is a directory."""

    result = validate_path(
        path,
        must_exist=True,
        allow_missing=False,
    )

    if not result.is_dir():
        raise SecurityError(
            f"Not a directory: {result}"
        )

    return result


def validate_file(path: str | Path) -> Path:
    """Validate that a path exists and is a regular file."""

    result = validate_path(
        path,
        must_exist=True,
        allow_missing=False,
    )

    if not result.is_file():
        raise SecurityError(
            f"Not a file: {result}"
        )

    return result


# ============================================================================
# COMMAND TOKENIZATION
# ============================================================================


def tokenize_command(command: str) -> List[str]:
    """
    Tokenize a command without executing it.

    Supports quoted arguments such as:

        cat "my project/file.txt"
    """

    if not isinstance(command, str):
        raise SecurityError("Command must be a string.")

    command = command.strip()

    if not command:
        raise SecurityError("Command cannot be empty.")

    try:
        return shlex.split(
            command,
            posix=(os.name != "nt"),
        )
    except ValueError as exc:
        raise SecurityError(
            f"Invalid command syntax: {exc}"
        ) from exc


def find_shell_operator(command: str) -> Optional[str]:
    """
    Find the first unquoted shell operator.

    Detection only. Nothing is executed.
    """

    operators = (
        "&&",
        "||",
        ">>",
        "|",
        ">",
        "<",
        ";",
        "&",
    )

    quote: Optional[str] = None
    escaped = False

    index = 0

    while index < len(command):
        char = command[index]

        if escaped:
            escaped = False
            index += 1
            continue

        if char == "\\":
            escaped = True
            index += 1
            continue

        if quote:
            if char == quote:
                quote = None

            index += 1
            continue

        if char in ("'", '"'):
            quote = char
            index += 1
            continue

        for operator in operators:
            if command.startswith(operator, index):
                return operator

        index += 1

    if quote:
        raise SecurityError(
            "Unclosed quote in command."
        )

    return None


def split_shell_segments(command: str) -> List[str]:
    """
    Split shell syntax into command/operator segments.

    Example:

        python app.py && echo done

    becomes:

        ["python app.py", "&&", "echo done"]

    This function only parses text.
    """

    segments: List[str] = []
    current: List[str] = []

    quote: Optional[str] = None
    escaped = False
    index = 0

    operators = (
        "&&",
        "||",
        ">>",
        "|",
        ">",
        "<",
        ";",
        "&",
    )

    while index < len(command):
        char = command[index]

        if escaped:
            current.append(char)
            escaped = False
            index += 1
            continue

        if char == "\\":
            current.append(char)
            escaped = True
            index += 1
            continue

        if quote:
            current.append(char)

            if char == quote:
                quote = None

            index += 1
            continue

        if char in ("'", '"'):
            quote = char
            current.append(char)
            index += 1
            continue

        matched = None

        for operator in operators:
            if command.startswith(operator, index):
                matched = operator
                break

        if matched:
            text = "".join(current).strip()

            if text:
                segments.append(text)

            segments.append(matched)
            current = []

            index += len(matched)
            continue

        current.append(char)
        index += 1

    if quote:
        raise SecurityError(
            "Unclosed quote in command."
        )

    text = "".join(current).strip()

    if text:
        segments.append(text)

    return segments


# ============================================================================
# EXECUTABLE INFORMATION
# ============================================================================


def resolve_executable(executable: str) -> Optional[str]:
    """
    Resolve an executable through PATH.

    This does not execute anything.
    """

    if not executable:
        return None

    return shutil.which(executable)


def executable_name(command: str) -> str:
    """Return the normalized executable name."""

    tokens = tokenize_command(command)

    if not tokens:
        raise SecurityError(
            "No executable found."
        )

    executable = Path(tokens[0]).name.lower()

    for suffix in (
        ".exe",
        ".cmd",
        ".bat",
        ".com",
        ".ps1",
    ):
        if executable.endswith(suffix):
            executable = executable[:-len(suffix)]
            break

    return executable


# ============================================================================
# DANGER DETECTION
# ============================================================================


def contains_dangerous_pattern(
    command: str,
) -> Optional[str]:
    """
    Check configured dangerous patterns.

    Returns the matching pattern or None.
    """

    lowered = command.lower()

    for pattern in config.DANGEROUS_PATTERNS:
        if str(pattern).lower() in lowered:
            return str(pattern)

    return None


def _dangerous_executable(executable: str) -> Optional[str]:
    """Check whether an executable is configured as dangerous."""

    dangerous_commands = {
        str(item).lower()
        for item in config.DANGEROUS_COMMANDS
    }

    if executable in dangerous_commands:
        return executable

    return None


def _dangerous_arguments(
    executable: str,
    arguments: List[str],
) -> Optional[str]:
    """
    Detect destructive argument combinations.

    This intentionally favors false positives over silently missing obvious
    destructive patterns when Maple is making the decision.
    """

    lowered_args = [
        str(argument).lower()
        for argument in arguments
    ]

    joined = " ".join(
        [executable] + lowered_args
    )

    checks = [
        (
            executable == "rm"
            and any(arg in {"-r", "-rf", "-fr", "-rfi"}
                    or arg.startswith("-rf")
                    for arg in lowered_args),
            "recursive rm",
        ),
        (
            executable in {"rmdir", "rd"}
            and any(
                arg in {"/s", "/q"}
                for arg in lowered_args
            ),
            "recursive directory deletion",
        ),
        (
            executable in {"del", "erase"}
            and any(
                arg in {"/s", "/q"}
                for arg in lowered_args
            ),
            "recursive/quiet deletion",
        ),
        (
            executable in {
                "format",
                "mkfs",
                "fdisk",
                "diskpart",
            },
            f"disk/filesystem operation: {executable}",
        ),
        (
            executable in {
                "shutdown",
                "reboot",
                "poweroff",
            },
            f"system power operation: {executable}",
        ),
        (
            executable in {
                "chmod",
                "chown",
            },
            f"permission operation: {executable}",
        ),
        (
            executable in {
                "mount",
                "umount",
            },
            f"mount operation: {executable}",
        ),
    ]

    for matched, reason in checks:
        if matched:
            return reason

    # Extra destructive combinations.
    if executable == "dd":
        return "raw disk/data operation"

    if executable in {"kill", "pkill", "killall", "taskkill"}:
        return f"process termination: {executable}"

    if ">" in joined and (
        "/dev/" in joined
        or "\\\\.\\physicaldrive" in joined
    ):
        return "direct device overwrite"

    return None


def is_dangerous_command(
    command: str,
) -> Tuple[bool, str]:
    """
    Determine whether a command appears potentially dangerous.

    Returns:

        (False, "")
        (True, reason)
    """

    command = command.strip()

    if not command:
        return False, ""

    pattern = contains_dangerous_pattern(command)

    if pattern:
        return (
            True,
            f"Dangerous pattern detected: {pattern}",
        )

    try:
        tokens = tokenize_command(command)
    except SecurityError as exc:
        return True, str(exc)

    if not tokens:
        return False, ""

    executable = executable_name(command)

    dangerous_executable = _dangerous_executable(
        executable
    )

    if dangerous_executable:
        return (
            True,
            f"Dangerous command: {dangerous_executable}",
        )

    reason = _dangerous_arguments(
        executable,
        tokens[1:],
    )

    if reason:
        return (
            True,
            f"Potentially dangerous operation: {reason}",
        )

    return False, ""


# ============================================================================
# COMMAND ANALYSIS
# ============================================================================


def analyze_command(
    command: str,
    *,
    source: str = "human",
) -> CommandAnalysis:
    """
    Analyze a command without executing it.

    source values commonly include:

        human
        maple
        system
    """

    tokens = tokenize_command(command)

    executable = executable_name(command)

    dangerous, reason = is_dangerous_command(
        command
    )

    operator = find_shell_operator(command)

    normalized_source = (
        str(source).strip().lower()
        or "human"
    )

    # Maple is the only source that automatically enters the
    # confirmation path.
    requires_confirmation = (
        normalized_source == "maple"
        and dangerous
    )

    return CommandAnalysis(
        command=command,
        executable=executable,
        arguments=tokens[1:],
        dangerous=dangerous,
        requires_confirmation=requires_confirmation,
        contains_shell_operator=operator is not None,
        shell_operator=operator,
        reason=reason,
        source=normalized_source,
    )


# ============================================================================
# COMMAND POLICY
# ============================================================================


def check_command(
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> CommandAnalysis:
    """
    Analyze a command and apply the appropriate policy.

    IMPORTANT:

        Human:
            Dangerous commands are NOT blocked here.

        Maple:
            Dangerous commands require confirmation.

    Shell parsing itself remains the responsibility of shell.py/executor.py.
    """

    analysis = analyze_command(
        command,
        source=source,
    )

    normalized_source = (
        str(source).strip().lower()
        or "human"
    )

    if (
        normalized_source == "maple"
        and analysis.dangerous
        and not confirmed
    ):
        raise PermissionDenied(
            analysis.reason
            or "Maple requires confirmation for this command."
        )

    return analysis


# ============================================================================
# OPERATION PERMISSIONS
# ============================================================================


def check_permission(
    operation: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> bool:
    """
    Check permission for a structured operation.

    Human operations:
        Allowed normally.

    Maple operations:
        Dangerous operations require confirmation.

    This function does not execute anything.
    """

    operation = (
        str(operation)
        .strip()
        .lower()
    )

    source = (
        str(source)
        .strip()
        .lower()
    )

    if not operation:
        raise SecurityError(
            "Operation cannot be empty."
        )

    dangerous_operations = {
        "delete",
        "remove",
        "rm",
        "overwrite",
        "replace",
        "format",
        "partition",
        "disk",
        "raw_disk",
        "shutdown",
        "reboot",
        "poweroff",
        "kill",
        "terminate",
        "admin",
        "privilege",
        "permission_change",
        "system_config",
    }

    is_dangerous = (
        operation in dangerous_operations
    )

    if source == "maple":
        if is_dangerous and not confirmed:
            raise PermissionDenied(
                f"Maple requires confirmation for "
                f"operation '{operation}'."
            )

    # Human execution is intentionally not blocked by
    # Maple's confirmation policy.
    return True


# ============================================================================
# FILE OPERATION SECURITY
# ============================================================================


def check_file_operation(
    operation: str,
    path: str | Path,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """
    Validate a filesystem operation before execution.

    Path validation is always performed.

    Dangerous-operation confirmation applies to Maple.
    """

    operation = (
        str(operation)
        .strip()
        .lower()
    )

    validated = validate_path(
        path,
        allow_missing=True,
    )

    if operation in {
        "delete",
        "remove",
        "rm",
        "rmdir",
    }:
        check_permission(
            "delete",
            source=source,
            confirmed=confirmed,
        )

    elif operation in {
        "write",
        "overwrite",
        "replace",
    }:
        if validated.exists():
            check_permission(
                "overwrite",
                source=source,
                confirmed=confirmed,
            )

    elif operation in {
        "format",
        "partition",
        "raw_disk",
    }:
        check_permission(
            operation,
            source=source,
            confirmed=confirmed,
        )

    return validated


# ============================================================================
# ENVIRONMENT SECURITY
# ============================================================================


def filter_environment(
    environment: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Return a controlled child-process environment.

    Only variables explicitly permitted by config.py are copied.

    PATH is preserved because external executables need it.
    """

    source = (
        environment
        if environment is not None
        else os.environ
    )

    allowed_names = {
        str(name).upper()
        for name in config.ALLOWED_ENVIRONMENT_VARIABLES
    }

    filtered: dict[str, str] = {}

    for key, value in source.items():
        if str(key).upper() in allowed_names:
            filtered[str(key)] = str(value)

    if "PATH" in source:
        filtered["PATH"] = str(source["PATH"])

    return filtered


# ============================================================================
# MAPLE ACTION VALIDATION
# ============================================================================


def validate_maple_action(
    action: dict,
    *,
    confirmed: bool = False,
) -> dict:
    """
    Validate a structured action produced by Maple.

    Example:

        {
            "type": "command",
            "command": "python app.py"
        }

    Supported conceptual action types include:

        command
        filesystem
        process
        package
        git
        shell

    This function validates/authorizes the action.
    It never executes it.
    """

    if not isinstance(action, dict):
        raise SecurityError(
            "Maple action must be a dictionary."
        )

    action_type = str(
        action.get("type", "")
    ).strip().lower()

    if not action_type:
        raise SecurityError(
            "Maple action has no type."
        )

    # ------------------------------------------------------------------
    # COMMAND
    # ------------------------------------------------------------------

    if action_type == "command":
        command = action.get("command")

        if (
            not isinstance(command, str)
            or not command.strip()
        ):
            raise SecurityError(
                "Maple command action requires a command string."
            )

        analysis = analyze_command(
            command,
            source="maple",
        )

        if (
            analysis.dangerous
            and not confirmed
        ):
            raise PermissionDenied(
                analysis.reason
                or "Maple command requires confirmation."
            )

        return {
            **action,
            "type": "command",
            "analysis": analysis,
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # FILESYSTEM
    # ------------------------------------------------------------------

    if action_type == "filesystem":
        operation = str(
            action.get("operation", "")
        ).strip().lower()

        path = action.get("path")

        if not operation:
            raise SecurityError(
                "Filesystem action has no operation."
            )

        if path is None:
            raise SecurityError(
                "Filesystem action has no path."
            )

        validated = check_file_operation(
            operation,
            path,
            source="maple",
            confirmed=confirmed,
        )

        return {
            **action,
            "type": "filesystem",
            "path": str(validated),
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # PROCESS
    # ------------------------------------------------------------------

    if action_type == "process":
        operation = str(
            action.get("operation", "")
        ).strip().lower()

        if not operation:
            raise SecurityError(
                "Process action has no operation."
            )

        check_permission(
            operation,
            source="maple",
            confirmed=confirmed,
        )

        return {
            **action,
            "type": "process",
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # PACKAGE
    # ------------------------------------------------------------------

    if action_type == "package":
        operation = str(
            action.get("operation", "install")
        ).strip().lower()

        # Installing packages can alter the environment, so Maple should
        # explicitly authorize the operation through its approval system.
        if operation in {
            "install",
            "remove",
            "upgrade",
            "uninstall",
        }:
            if not confirmed:
                raise PermissionDenied(
                    f"Maple requires confirmation for "
                    f"package operation '{operation}'."
                )

        return {
            **action,
            "type": "package",
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # GIT
    # ------------------------------------------------------------------

    if action_type == "git":
        operation = str(
            action.get("operation", "")
        ).strip().lower()

        if operation in {
            "reset",
            "clean",
            "push",
            "force_push",
            "delete",
        } and not confirmed:
            raise PermissionDenied(
                f"Maple requires confirmation for "
                f"git operation '{operation}'."
            )

        return {
            **action,
            "type": "git",
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # SHELL
    # ------------------------------------------------------------------

    if action_type == "shell":
        command = action.get("command")

        if (
            not isinstance(command, str)
            or not command.strip()
        ):
            raise SecurityError(
                "Shell action requires a command string."
            )

        analysis = analyze_command(
            command,
            source="maple",
        )

        if (
            analysis.dangerous
            and not confirmed
        ):
            raise PermissionDenied(
                analysis.reason
                or "Maple shell action requires confirmation."
            )

        return {
            **action,
            "type": "shell",
            "analysis": analysis,
            "confirmed": confirmed,
        }

    # ------------------------------------------------------------------
    # UNKNOWN ACTION
    # ------------------------------------------------------------------

    raise SecurityError(
        f"Unsupported Maple action type: {action_type}"
    )


# ============================================================================
# CONVENIENCE API
# ============================================================================


def requires_confirmation(
    command: str,
    *,
    source: str = "maple",
) -> bool:
    """
    Return whether a command requires confirmation.

    This is intentionally non-throwing.
    """

    try:
        analysis = analyze_command(
            command,
            source=source,
        )
    except SecurityError:
        return True

    return analysis.requires_confirmation


def authorize_command(
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> CommandAnalysis:
    """
    Analyze and authorize a command.

    Human:
        Returns analysis normally.

    Maple:
        Raises PermissionDenied for dangerous commands unless confirmed.
    """

    return check_command(
        command,
        source=source,
        confirmed=confirmed,
    )


def validate_command_syntax(
    command: str,
) -> bool:
    """
    Validate command syntax without applying execution policy.
    """

    tokenize_command(command)
    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    "SecurityError",
    "PermissionDenied",
    "CommandAnalysis",
    "validate_path",
    "validate_directory",
    "validate_file",
    "tokenize_command",
    "find_shell_operator",
    "split_shell_segments",
    "resolve_executable",
    "executable_name",
    "contains_dangerous_pattern",
    "is_dangerous_command",
    "analyze_command",
    "check_command",
    "check_permission",
    "check_file_operation",
    "filter_environment",
    "validate_maple_action",
    "requires_confirmation",
    "authorize_command",
    "validate_command_syntax",
]

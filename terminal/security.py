"""
Convexity Security and Permission Layer
Version 0.2.0

Responsibilities:
- Validate filesystem paths
- Enforce optional sandbox boundaries
- Inspect commands before execution
- Detect dangerous operations
- Handle shell operators
- Provide human/Maple permission checks
- Prevent obvious command-policy bypasses

Security is a policy layer, not a replacement for the terminal engine.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .config import config


class SecurityError(Exception):
    """Base exception for Convexity security violations."""


class PermissionDenied(SecurityError):
    """Raised when an operation requires permission or confirmation."""


@dataclass
class CommandAnalysis:
    """Result of analyzing a command before execution."""

    command: str
    executable: str
    arguments: List[str]
    dangerous: bool = False
    requires_confirmation: bool = False
    contains_shell_operator: bool = False
    shell_operator: Optional[str] = None
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return not self.dangerous


# ---------------------------------------------------------------------------
# PATH SECURITY
# ---------------------------------------------------------------------------

def validate_path(
    path: str | Path,
    *,
    must_exist: bool = False,
    allow_missing: bool = True,
) -> Path:
    """
    Resolve and validate a filesystem path.

    If sandboxing is enabled, the resulting path must remain inside
    Convexity's configured sandbox root.
    """

    if not path:
        raise SecurityError("Path cannot be empty.")

    path_obj = Path(path).expanduser()

    try:
        if path_obj.exists():
            resolved = path_obj.resolve(strict=True)
        else:
            if not allow_missing:
                raise SecurityError(f"Path does not exist: {path}")

            # Resolve the parent when possible so '..' is normalized.
            parent = path_obj.parent

            if parent.exists():
                resolved = parent.resolve() / path_obj.name
            else:
                resolved = path_obj.resolve(strict=False)

    except OSError as exc:
        raise SecurityError(f"Unable to resolve path: {path}") from exc

    if len(str(resolved)) > config.MAX_PATH_LENGTH:
        raise SecurityError("Path exceeds Convexity's maximum path length.")

    if must_exist and not resolved.exists():
        raise SecurityError(f"Path does not exist: {resolved}")

    if config.SANDBOX_ENABLED:
        sandbox_root = Path(config.get_sandbox_root()).resolve()

        try:
            resolved.relative_to(sandbox_root)
        except ValueError as exc:
            raise SecurityError(
                f"Access outside the Convexity sandbox is blocked:\n"
                f"{resolved}"
            ) from exc

    return resolved


def validate_directory(path: str | Path) -> Path:
    """Validate that a path exists and is a directory."""

    result = validate_path(path, must_exist=True)

    if not result.is_dir():
        raise SecurityError(f"Not a directory: {result}")

    return result


def validate_file(path: str | Path) -> Path:
    """Validate that a path exists and is a file."""

    result = validate_path(path, must_exist=True)

    if not result.is_file():
        raise SecurityError(f"Not a file: {result}")

    return result


# ---------------------------------------------------------------------------
# COMMAND PARSING
# ---------------------------------------------------------------------------

def tokenize_command(command: str) -> List[str]:
    """
    Safely tokenize a command without executing it.

    shlex is used instead of command.split(), allowing quoted paths such as:

        cat "my project/file.txt"
    """

    if not isinstance(command, str):
        raise SecurityError("Command must be a string.")

    command = command.strip()

    if not command:
        raise SecurityError("Command cannot be empty.")

    try:
        return shlex.split(command, posix=(os.name != "nt"))
    except ValueError as exc:
        raise SecurityError(f"Invalid command syntax: {exc}") from exc


def find_shell_operator(command: str) -> Optional[str]:
    """
    Detect common shell operators.

    This function only identifies operators.
    It does not execute them.
    """

    operators = (
        "&&",
        "||",
        ">>",
        "|",
        ">",
        "<",
        ";",
    )

    quote = None
    escaped = False

    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if quote:
            if char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            continue

        remaining = command[index:]

        for operator in operators:
            if remaining.startswith(operator):
                return operator

    return None


def split_shell_segments(command: str) -> List[str]:
    """
    Split a command into shell segments.

    This is intentionally conservative. A future Convexity parser can replace
    this with a complete shell grammar.
    """

    segments = []
    current = []
    quote = None
    escaped = False
    index = 0

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

        for operator in ("&&", "||", ">>", "|", ">", "<", ";"):
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

    text = "".join(current).strip()

    if text:
        segments.append(text)

    if quote:
        raise SecurityError("Unclosed quote in command.")

    return segments


# ---------------------------------------------------------------------------
# EXECUTABLE SECURITY
# ---------------------------------------------------------------------------

def resolve_executable(executable: str) -> Optional[str]:
    """
    Resolve an executable through PATH without executing it.
    """

    if not executable:
        return None

    return shutil.which(executable)


def executable_name(command: str) -> str:
    """Return the executable portion of a command."""

    tokens = tokenize_command(command)

    if not tokens:
        raise SecurityError("No executable found.")

    executable = Path(tokens[0]).name.lower()

    # Windows executable suffixes.
    for suffix in (".exe", ".cmd", ".bat", ".com", ".ps1"):
        if executable.endswith(suffix):
            executable = executable[: -len(suffix)]
            break

    return executable


# ---------------------------------------------------------------------------
# DANGEROUS COMMAND DETECTION
# ---------------------------------------------------------------------------

def contains_dangerous_pattern(command: str) -> Optional[str]:
    """
    Search for dangerous command patterns configured in config.py.
    """

    lowered = command.lower()

    for pattern in config.DANGEROUS_PATTERNS:
        if pattern.lower() in lowered:
            return pattern

    return None


def is_dangerous_command(command: str) -> Tuple[bool, str]:
    """
    Determine whether a command appears dangerous.

    Returns:
        (True, reason)
        (False, "")
    """

    command = command.strip()

    if not command:
        return False, ""

    pattern = contains_dangerous_pattern(command)

    if pattern:
        return True, f"Dangerous pattern detected: {pattern}"

    try:
        tokens = tokenize_command(command)
    except SecurityError as exc:
        return True, str(exc)

    if not tokens:
        return False, ""

    executable = executable_name(command)

    dangerous_commands = {
        str(item).lower()
        for item in config.DANGEROUS_COMMANDS
    }

    if executable in dangerous_commands:
        return True, f"Dangerous command: {executable}"

    # Additional destructive argument checks.
    lowered = command.lower()

    destructive_combinations = [
        ("rm", "-rf"),
        ("rm", "-r"),
        ("rmdir", "/s"),
        ("del", "/s"),
        ("del", "/q"),
        ("format",),
        ("mkfs",),
        ("fdisk",),
        ("diskpart",),
        ("shutdown",),
        ("reboot",),
        ("poweroff",),
        ("chmod",),
        ("chown",),
        ("mount",),
        ("umount",),
    ]

    for combination in destructive_combinations:
        if len(combination) == 1:
            if re.search(
                rf"(^|\s){re.escape(combination[0])}(\s|$)",
                lowered,
            ):
                return True, f"Potentially destructive command: {combination[0]}"

        elif all(part in lowered for part in combination):
            return True, (
                "Potentially destructive command combination: "
                + " ".join(combination)
            )

    return False, ""


# ---------------------------------------------------------------------------
# COMMAND ANALYSIS
# ---------------------------------------------------------------------------

def analyze_command(
    command: str,
    *,
    source: str = "human",
) -> CommandAnalysis:
    """
    Analyze a command without executing it.

    source:
        human
        maple
        system
    """

    tokens = tokenize_command(command)

    executable = executable_name(command)

    dangerous, reason = is_dangerous_command(command)

    operator = find_shell_operator(command)

    requires_confirmation = (
        dangerous
        or (
            source.lower() == "maple"
            and config.MAPLE_REQUIRE_PERMISSION
        )
    )

    # Maple should not bypass the security layer simply because shell
    # commands are enabled.
    if source.lower() == "maple" and config.MAPLE_REQUIRE_PERMISSION:
        requires_confirmation = True

    return CommandAnalysis(
        command=command,
        executable=executable,
        arguments=tokens[1:],
        dangerous=dangerous,
        requires_confirmation=requires_confirmation,
        contains_shell_operator=operator is not None,
        shell_operator=operator,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# COMMAND POLICY
# ---------------------------------------------------------------------------

def check_command(
    command: str,
    *,
    source: str = "human",
) -> CommandAnalysis:
    """
    Validate a command against Convexity's current policy.

    Human users can eventually use the full native Convexity shell.

    Maple requests are always routed through the permission layer when
    MAPLE_REQUIRE_PERMISSION is enabled.
    """

    analysis = analyze_command(command, source=source)

    # Always block configured dangerous patterns at this layer.
    if analysis.dangerous:
        raise PermissionDenied(
            analysis.reason or "Command blocked by security policy."
        )

    # Shell operators are handled by the future shell parser.
    # Do not silently pass them to subprocess as one executable.
    if analysis.contains_shell_operator:
        if not config.ALLOW_SHELL_COMMANDS:
            raise PermissionDenied(
                f"Shell operator '{analysis.shell_operator}' "
                "is disabled by configuration."
            )

    return analysis


# ---------------------------------------------------------------------------
# OPERATION PERMISSIONS
# ---------------------------------------------------------------------------

def check_permission(
    operation: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> bool:
    """
    Check whether an operation may proceed.

    Human operations:
        Normal terminal operations are allowed unless explicitly dangerous.

    Maple operations:
        Require an explicit permission decision when configured.
    """

    operation = operation.lower().strip()
    source = source.lower().strip()

    dangerous_operations = {
        "delete",
        "overwrite",
        "execute_dangerous",
        "format",
        "partition",
        "shutdown",
        "reboot",
        "admin",
        "permission_change",
    }

    if operation in dangerous_operations:
        if not confirmed:
            raise PermissionDenied(
                f"Operation '{operation}' requires confirmation."
            )

    if source == "maple" and config.MAPLE_REQUIRE_PERMISSION:
        if not confirmed:
            raise PermissionDenied(
                f"Maple requires permission for operation '{operation}'."
            )

    return True


# ---------------------------------------------------------------------------
# FILE OPERATION PERMISSIONS
# ---------------------------------------------------------------------------

def check_file_operation(
    operation: str,
    path: str | Path,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> Path:
    """
    Validate a filesystem operation before it reaches filesystem.py.
    """

    validated = validate_path(path, allow_missing=True)

    operation = operation.lower().strip()

    if operation in {"delete", "remove", "rm"}:
        check_permission(
            "delete",
            source=source,
            confirmed=confirmed,
        )

    elif operation in {"write", "overwrite", "replace"}:
        if validated.exists():
            check_permission(
                "overwrite",
                source=source,
                confirmed=confirmed,
            )

    return validated


# ---------------------------------------------------------------------------
# ENVIRONMENT SECURITY
# ---------------------------------------------------------------------------

def filter_environment(
    environment: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Create a controlled environment for child processes.

    Only explicitly approved variables are copied from the host environment.
    This prevents accidental exposure of arbitrary secrets to commands.
    """

    source = environment if environment is not None else os.environ

    allowed_names = {
        name.upper()
        for name in config.ALLOWED_ENVIRONMENT_VARIABLES
    }

    filtered: dict[str, str] = {}

    for key, value in source.items():
        if key.upper() in allowed_names:
            filtered[key] = value

    # Preserve the essential executable search path.
    if "PATH" in source:
        filtered["PATH"] = source["PATH"]

    return filtered


# ---------------------------------------------------------------------------
# MAPLE ACTION VALIDATION
# ---------------------------------------------------------------------------

def validate_maple_action(
    action: dict,
    *,
    confirmed: bool = False,
) -> dict:
    """
    Validate a structured action generated by Maple.

    Example:

        {
            "type": "command",
            "command": "python script.py"
        }

    Future action types can include:

        filesystem
        process
        package
        network
        git
        shell
    """

    if not isinstance(action, dict):
        raise SecurityError("Maple action must be an object/dictionary.")

    action_type = str(action.get("type", "")).strip().lower()

    if not action_type:
        raise SecurityError("Maple action has no type.")

    if action_type == "command":
        command = action.get("command")

        if not isinstance(command, str) or not command.strip():
            raise SecurityError("Maple command action has no command.")

        analysis = check_command(
            command,
            source="maple",
        )

        check_permission(
            "execute",
            source="maple",
            confirmed=confirmed,
        )

        return {
            "allowed": True,
            "type": "command",
            "command": command,
            "executable": analysis.executable,
            "arguments": analysis.arguments,
        }

    if action_type == "filesystem":
        operation = str(action.get("operation", "")).strip()
        path = action.get("path")

        if not operation:
            raise SecurityError("Filesystem action has no operation.")

        if not path:
            raise SecurityError("Filesystem action has no path.")

        validated = check_file_operation(
            operation,
            path,
            source="maple",
            confirmed=confirmed,
        )

        return {
            "allowed": True,
            "type": "filesystem",
            "operation": operation,
            "path": str(validated),
        }

    raise SecurityError(
        f"Unsupported Maple action type: {action_type}"
    )


# ---------------------------------------------------------------------------
# PUBLIC HELPERS
# ---------------------------------------------------------------------------

def is_path_safe(path: str | Path) -> bool:
    """Return True if a path passes Convexity's path policy."""

    try:
        validate_path(path)
        return True
    except SecurityError:
        return False


def is_command_safe(command: str) -> bool:
    """Return True if a command passes the current security policy."""

    try:
        check_command(command)
        return True
    except SecurityError:
        return False


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
    "is_path_safe",
    "is_command_safe",
]
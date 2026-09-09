"""
Convexity Security Layer.

Validates commands, checks permissions, and enforces sandbox constraints.
Prevents arbitrary code execution and path traversal attacks.
"""

import os
import shlex
from pathlib import Path
from typing import Tuple, Optional

from .config import config


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


class PermissionError(SecurityError):
    """Raised when an action requires confirmation or is forbidden."""
    pass


def validate_path(path_str: str) -> Path:
    """
    Validates and normalizes a file path, ensuring it stays within the sandbox.
    
    Args:
        path_str: The user-provided path string.
        
    Returns:
        A resolved Path object.
        
    Raises:
        SecurityError: If the path attempts to escape the sandbox.
    """
    if not config.SANDBOX_ENABLED:
        return Path(path_str).resolve()

    sandbox_root = Path(config.get_sandbox_root()).resolve()
    target_path = Path(path_str).resolve()

    # Check if the resolved path is relative to the sandbox root
    try:
        target_path.relative_to(sandbox_root)
    except ValueError:
        raise SecurityError(
            f"Access denied: Path '{path_str}' resolves outside the allowed sandbox "
            f"'{sandbox_root}'. Sandbox mode is enabled."
        )
    
    return target_path


def check_command(command_str: str) -> Tuple[bool, str]:
    """
    Checks if a command string is allowed to execute.
    
    Args:
        command_str: The full command string.
        
    Returns:
        A tuple (is_allowed, reason).
    """
    if not command_str.strip():
        return False, "Empty command"

    try:
        # Use shlex to safely split the command without executing it
        parts = shlex.split(command_str)
    except ValueError:
        return False, "Invalid command syntax (unmatched quotes?)"

    if not parts:
        return False, "Empty command"

    base_cmd = parts[0].lower()

    # 1. Check against dangerous patterns
    for pattern in config.DANGEROUS_PATTERNS:
        if pattern in command_str.lower():
            return False, f"Command blocked: Contains dangerous pattern '{pattern}'"

    # 2. Check Allowlist for external commands
    # Note: Built-in commands (ls, cd, etc.) are handled by filesystem.py 
    # and don't pass through this specific subprocess check usually, 
    # but if they did, they aren't in ALLOWED_EXTERNAL_COMMANDS.
    # This check is primarily for 'execute_command' actions passed to executor.
    
    if config.ALLOW_SHELL_COMMANDS:
        # If shell commands are globally allowed, we still check dangerous patterns
        return True, "Allowed"
    
    if base_cmd in config.ALLOWED_EXTERNAL_COMMANDS:
        return True, "Allowed"
    
    return False, f"Command '{base_cmd}' is not in the allowlist. Shell execution is disabled."


def check_permission(action: str) -> bool:
    """
    Checks if a specific action requires user confirmation.
    
    Args:
        action: The name of the action (e.g., 'delete', 'execute').
        
    Returns:
        True if permission is granted (or not required), False if confirmation needed.
    """
    dangerous_actions = {'delete', 'overwrite', 'execute_dangerous'}
    
    if action in dangerous_actions and config.REQUIRE_CONFIRMATION_FOR_DANGEROUS_ACTIONS:
        return False
        
    return True


def is_dangerous(command_str: str) -> bool:
    """
    Heuristic check for dangerous commands.
    
    Args:
        command_str: The command string.
        
    Returns:
        True if potentially dangerous.
    """
    for pattern in config.DANGEROUS_PATTERNS:
        if pattern in command_str.lower():
            return True
    return False

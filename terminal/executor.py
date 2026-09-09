"""
Convexity Command Executor.

Executes validated external commands using subprocess.
Captures stdout, stderr, and return codes.
Enforces timeouts and security constraints.
"""

import subprocess
import shlex
from typing import Dict, Any, Optional

from .security import check_command, SecurityError
from .config import config


class ExecutionResult:
    """Structured result of a command execution."""
    
    def __init__(self, success: bool, stdout: str, stderr: str, return_code: int):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code
        }

    def __str__(self):
        output = []
        if self.stdout:
            output.append(self.stdout)
        if self.stderr:
            output.append(self.stderr)
        return "\n".join(output) if output else ""


def execute_command(command_str: str) -> ExecutionResult:
    """
    Executes a validated external command.
    
    Args:
        command_str: The command string to execute.
        
    Returns:
        An ExecutionResult object.
    """
    # 1. Security Check
    is_allowed, reason = check_command(command_str)
    if not is_allowed:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Security Block: {reason}",
            return_code=-1
        )

    try:
        # 2. Parse Command
        # Using shlex.split for safe argument parsing
        args = shlex.split(command_str)
        if not args:
            raise ValueError("Empty command")

        # 3. Execute
        # Note: We do NOT use shell=True to prevent injection attacks.
        # We rely on the allowlist in security.py to permit specific binaries.
        process = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=config.DEFAULT_TIMEOUT,
            env=None  # Use current environment, could be restricted further
        )

        # 4. Process Output
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        
        # Truncate output if necessary
        if len(stdout) > config.MAX_OUTPUT_LENGTH:
            stdout = stdout[:config.MAX_OUTPUT_LENGTH] + "\n... [Output Truncated]"
        if len(stderr) > config.MAX_OUTPUT_LENGTH:
            stderr = stderr[:config.MAX_OUTPUT_LENGTH] + "\n... [Output Truncated]"

        return ExecutionResult(
            success=(process.returncode == 0),
            stdout=stdout,
            stderr=stderr,
            return_code=process.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Command timed out after {config.DEFAULT_TIMEOUT} seconds.",
            return_code=-1
        )
    except FileNotFoundError:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Command not found: {args[0]}",
            return_code=-1
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Execution Error: {str(e)}",
            return_code=-1
        )

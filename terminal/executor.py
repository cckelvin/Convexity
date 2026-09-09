"""
Convexity Command Executor
Version: 0.3.0

High-level command execution layer.

Architecture:

    Maple / Terminal
          |
          v
      Executor
          |
          v
      Security
          |
          v
    ProcessManager
          |
          v
    ManagedProcess
          |
          +---- subprocess
          |
          +---- PTY
          |
          v
    Operating System

Important:
- Executor does NOT create subprocesses directly.
- Process management belongs to terminal/process.py.
- Security analysis happens before execution.
- Human terminal commands are not subject to Maple approval.
- Maple commands can require confirmation.
"""

from __future__ import annotations

import os
import subprocess
import time

from dataclasses import dataclass
from typing import List, Optional

from .config import config
from .security import (
    PermissionDenied,
    SecurityError,
    check_command,
    filter_environment,
    split_shell_segments,
)
from .process import (
    ProcessManager,
    ManagedProcess,
    ProcessInfo,
    ProcessState,
    process_manager,
)


__version__ = "0.3.0"


# ============================================================================
# RESULT
# ============================================================================

@dataclass
class ExecutionResult:
    """
    Structured result returned by the Convexity execution layer.
    """

    success: bool

    stdout: str = ""

    stderr: str = ""

    return_code: int = 0

    command: str = ""

    duration: float = 0.0

    timed_out: bool = False

    pid: Optional[int] = None

    process_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "command": self.command,
            "duration": self.duration,
            "timed_out": self.timed_out,
            "pid": self.pid,
            "process_id": self.process_id,
        }

    def __str__(self) -> str:
        output = []

        if self.stdout:
            output.append(self.stdout)

        if self.stderr:
            output.append(self.stderr)

        if not output:
            output.append(
                f"[exit code: {self.return_code}]"
            )

        return "\n".join(output)


# ============================================================================
# EXECUTOR
# ============================================================================

class CommandExecutor:
    """
    Main Convexity command execution engine.

    This class is intentionally high-level.

    It does not directly create subprocesses.

    Process creation and lifecycle management are delegated to
    terminal.process.ProcessManager.
    """

    def __init__(
        self,
        manager: Optional[ProcessManager] = None,
    ) -> None:

        self.process_manager = (
            manager
            if manager is not None
            else process_manager
        )

    # ========================================================================
    # EXECUTE
    # ========================================================================

    def execute(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
        source: str = "human",
        confirmed: bool = False,
        timeout: Optional[float] = None,
        interactive: bool = False,
        callback=None,
    ) -> ExecutionResult:

        command = command.strip()

        if not command:
            return ExecutionResult(
                success=False,
                stderr="Empty command.",
                return_code=1,
                command=command,
            )

        start_time = time.monotonic()

        try:

            # ----------------------------------------------------------------
            # SECURITY ANALYSIS
            # ----------------------------------------------------------------

            analysis = check_command(
                command,
                source=source,
            )

            # ----------------------------------------------------------------
            # MAPLE APPROVAL
            # ----------------------------------------------------------------

            if source.lower() == "maple":

                if (
                    config.MAPLE_REQUIRE_PERMISSION
                    and not confirmed
                ):
                    raise PermissionDenied(
                        "Maple requires permission before execution."
                    )

            # ----------------------------------------------------------------
            # COMMAND
            # ----------------------------------------------------------------

            tokens = [
                analysis.executable,
                *analysis.arguments,
            ]

            # ----------------------------------------------------------------
            # ENVIRONMENT
            # ----------------------------------------------------------------

            env = filter_environment(
                environment
            )

            # ----------------------------------------------------------------
            # WORKING DIRECTORY
            # ----------------------------------------------------------------

            if cwd is not None:

                cwd = os.path.abspath(
                    os.path.expanduser(cwd)
                )

                if not os.path.isdir(cwd):

                    return ExecutionResult(
                        success=False,
                        stderr=(
                            "Working directory does not exist: "
                            f"{cwd}"
                        ),
                        return_code=1,
                        command=command,
                    )

            # ----------------------------------------------------------------
            # TIMEOUT
            # ----------------------------------------------------------------

            effective_timeout = (
                timeout
                if timeout is not None
                else config.DEFAULT_TIMEOUT
            )

            # ----------------------------------------------------------------
            # START PROCESS
            # ----------------------------------------------------------------

            process = self.process_manager.start(
                tokens,
                interactive=interactive,
                background=False,
                cwd=cwd,
                env=env,
                callback=callback,
            )

            # ----------------------------------------------------------------
            # WAIT
            # ----------------------------------------------------------------

            try:

                return_code = process.wait(
                    timeout=effective_timeout
                )

            except subprocess.TimeoutExpired:

                process.kill()

                try:
                    process.wait(
                        timeout=2
                    )
                except Exception:
                    pass

                duration = (
                    time.monotonic()
                    - start_time
                )

                return ExecutionResult(
                    success=False,
                    stdout=self._limit_output(
                        process.stdout()
                    ),
                    stderr=(
                        self._limit_output(
                            process.stderr()
                        )
                        + "\nCommand timed out."
                    ).strip(),
                    return_code=-1,
                    command=command,
                    duration=duration,
                    timed_out=True,
                    pid=process.pid,
                    process_id=process.process_id,
                )

            # ----------------------------------------------------------------
            # RESULT
            # ----------------------------------------------------------------

            duration = (
                time.monotonic()
                - start_time
            )

            stdout = self._limit_output(
                process.stdout()
            )

            stderr = self._limit_output(
                process.stderr()
            )

            return ExecutionResult(
                success=(return_code == 0),
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                command=command,
                duration=duration,
                pid=process.pid,
                process_id=process.process_id,
            )

        # ====================================================================
        # ERRORS
        # ====================================================================

        except PermissionDenied as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Permission denied: {exc}",
                return_code=126,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except SecurityError as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Security error: {exc}",
                return_code=126,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except FileNotFoundError:

            executable = (
                command.split()[0]
                if command.split()
                else command
            )

            return ExecutionResult(
                success=False,
                stderr=f"Command not found: {executable}",
                return_code=127,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except PermissionError:

            return ExecutionResult(
                success=False,
                stderr=(
                    "Operating system denied permission "
                    "to execute command."
                ),
                return_code=126,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except OSError as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Operating system error: {exc}",
                return_code=1,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except Exception as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Execution error: {exc}",
                return_code=1,
                command=command,
                duration=time.monotonic() - start_time,
            )

    # ========================================================================
    # INTERACTIVE
    # ========================================================================

    def execute_interactive(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
        source: str = "human",
        confirmed: bool = False,
        callback=None,
    ) -> ExecutionResult:

        return self.execute(
            command,
            cwd=cwd,
            environment=environment,
            source=source,
            confirmed=confirmed,
            interactive=True,
            callback=callback,
        )

    # ========================================================================
    # BACKGROUND
    # ========================================================================

    def start_background(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
        source: str = "human",
        confirmed: bool = False,
        interactive: bool = False,
        callback=None,
    ) -> ExecutionResult:

        command = command.strip()

        if not command:
            return ExecutionResult(
                success=False,
                stderr="Empty command.",
                return_code=1,
                command=command,
            )

        try:

            # ---------------------------------------------------------------
            # SECURITY
            # ---------------------------------------------------------------

            analysis = check_command(
                command,
                source=source,
            )

            # ---------------------------------------------------------------
            # MAPLE APPROVAL
            # ---------------------------------------------------------------

            if source.lower() == "maple":

                if (
                    config.MAPLE_REQUIRE_PERMISSION
                    and not confirmed
                ):
                    raise PermissionDenied(
                        "Maple requires permission before "
                        "starting a process."
                    )

            # ---------------------------------------------------------------
            # COMMAND
            # ---------------------------------------------------------------

            tokens = [
                analysis.executable,
                *analysis.arguments,
            ]

            # ---------------------------------------------------------------
            # ENVIRONMENT
            # ---------------------------------------------------------------

            env = filter_environment(
                environment
            )

            # ---------------------------------------------------------------
            # CWD
            # ---------------------------------------------------------------

            if cwd is not None:

                cwd = os.path.abspath(
                    os.path.expanduser(cwd)
                )

                if not os.path.isdir(cwd):

                    return ExecutionResult(
                        success=False,
                        stderr=(
                            "Working directory does not exist: "
                            f"{cwd}"
                        ),
                        return_code=1,
                        command=command,
                    )

            # ---------------------------------------------------------------
            # START
            # ---------------------------------------------------------------

            process = self.process_manager.start(
                tokens,
                interactive=interactive,
                background=True,
                cwd=cwd,
                env=env,
                callback=callback,
            )

            return ExecutionResult(
                success=True,
                stdout=(
                    f"Process started: "
                    f"ID {process.process_id}"
                ),
                return_code=0,
                command=command,
                pid=process.pid,
                process_id=process.process_id,
            )

        except PermissionDenied as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Permission denied: {exc}",
                return_code=126,
                command=command,
            )

        except SecurityError as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Security error: {exc}",
                return_code=126,
                command=command,
            )

        except FileNotFoundError:

            return ExecutionResult(
                success=False,
                stderr="Command not found.",
                return_code=127,
                command=command,
            )

        except Exception as exc:

            return ExecutionResult(
                success=False,
                stderr=(
                    f"Unable to start process: {exc}"
                ),
                return_code=1,
                command=command,
            )

    # ========================================================================
    # PIPELINES
    # ========================================================================

    def execute_pipeline(
        self,
        commands: List[str],
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:

        """
        Execute a pipeline.

        Pipeline process wiring is intentionally delegated to the process
        layer in the next process-manager enhancement.

        We do not recreate subprocess.Popen here because that would
        reintroduce the architecture duplication we are removing.
        """

        if not commands:

            return ExecutionResult(
                success=False,
                stderr="Pipeline is empty.",
                return_code=1,
            )

        if len(commands) == 1:

            return self.execute(
                commands[0],
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

        return ExecutionResult(
            success=False,
            stderr=(
                "Pipeline execution is temporarily unavailable "
                "while the canonical process pipeline layer is being "
                "integrated."
            ),
            return_code=2,
            command=" | ".join(commands),
        )

    # ========================================================================
    # SHELL SEGMENTS
    # ========================================================================

    def execute_shell_segments(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:

        segments = split_shell_segments(
            command
        )

        if not segments:

            return ExecutionResult(
                success=False,
                stderr="Empty command.",
                return_code=1,
                command=command,
            )

        # ---------------------------------------------------------------
        # PIPELINE
        # ---------------------------------------------------------------

        if "|" in segments:

            if any(
                operator in segments
                for operator in (
                    "&&",
                    "||",
                    ";",
                    ">",
                    ">>",
                    "<",
                )
            ):

                return ExecutionResult(
                    success=False,
                    stderr=(
                        "Mixed shell operators are not yet handled "
                        "by the Convexity shell engine."
                    ),
                    return_code=2,
                    command=command,
                )

            pipeline = [
                item
                for item in segments
                if item != "|"
            ]

            return self.execute_pipeline(
                pipeline,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

        # ---------------------------------------------------------------
        # UNSUPPORTED OPERATORS
        # ---------------------------------------------------------------

        operators = {
            "&&",
            "||",
            ";",
            ">",
            ">>",
            "<",
        }

        if any(
            segment in operators
            for segment in segments
        ):

            return ExecutionResult(
                success=False,
                stderr=(
                    "This shell operator requires the Convexity "
                    "shell parser and redirection engine."
                ),
                return_code=2,
                command=command,
            )

        return self.execute(
            command,
            cwd=cwd,
            source=source,
            confirmed=confirmed,
        )

    # ========================================================================
    # PROCESS CONTROL
    # ========================================================================

    def get_process(
        self,
        process_id: int,
    ) -> Optional[ManagedProcess]:

        return self.process_manager.get(
            process_id
        )

    def terminate(
        self,
        process_id: int,
    ) -> bool:

        return self.process_manager.terminate(
            process_id
        )

    def kill(
        self,
        process_id: int,
    ) -> bool:

        return self.process_manager.kill(
            process_id
        )

    def send_signal(
        self,
        process_id: int,
        signal_number: int,
    ) -> bool:

        return self.process_manager.send_signal(
            process_id,
            signal_number,
        )

    def wait(
        self,
        process_id: int,
        timeout: Optional[float] = None,
    ) -> int:

        return self.process_manager.wait(
            process_id,
            timeout=timeout,
        )

    def write(
        self,
        process_id: int,
        data: str,
    ) -> bool:

        return self.process_manager.write(
            process_id,
            data,
        )

    def list_processes(
        self,
        *,
        include_finished: bool = True,
    ) -> List[ProcessInfo]:

        return self.process_manager.list(
            include_finished=include_finished
        )

    def remove_finished_processes(self) -> int:

        return self.process_manager.remove_finished()

    # ========================================================================
    # OUTPUT LIMIT
    # ========================================================================

    @staticmethod
    def _limit_output(
        output: str,
    ) -> str:

        if not output:
            return ""

        max_bytes = config.MAX_OUTPUT_SIZE

        encoded = output.encode(
            "utf-8",
            errors="replace",
        )

        if len(encoded) <= max_bytes:
            return output

        truncated = encoded[
            :max_bytes
        ].decode(
            "utf-8",
            errors="replace",
        )

        return (
            truncated
            + "\n[output truncated by Convexity]"
        )


# ============================================================================
# GLOBAL EXECUTOR
# ============================================================================

executor = CommandExecutor()


# ============================================================================
# CONVENIENCE API
# ============================================================================

def execute(
    command: str,
    **kwargs,
) -> ExecutionResult:

    return executor.execute(
        command,
        **kwargs,
    )


def start_background(
    command: str,
    **kwargs,
) -> ExecutionResult:

    return executor.start_background(
        command,
        **kwargs,
    )


def execute_interactive(
    command: str,
    **kwargs,
) -> ExecutionResult:

    return executor.execute_interactive(
        command,
        **kwargs,
    )


def execute_pipeline(
    commands: List[str],
    **kwargs,
) -> ExecutionResult:

    return executor.execute_pipeline(
        commands,
        **kwargs,
    )


__all__ = [
    "ExecutionResult",
    "CommandExecutor",
    "executor",
    "execute",
    "start_background",
    "execute_interactive",
    "execute_pipeline",
]

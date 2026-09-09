"""
Convexity Command Executor
Version 0.2.0

Executes commands approved by Convexity's security layer.

This module is intentionally separate from the shell parser so Convexity
can eventually support its own shell language, pipelines, redirection,
background jobs, and Maple actions.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import config
from .security import (
    PermissionDenied,
    SecurityError,
    check_command,
    filter_environment,
    split_shell_segments,
)


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Structured result returned after command execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    command: str = ""
    duration: float = 0.0
    timed_out: bool = False
    pid: Optional[int] = None

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


# ---------------------------------------------------------------------------
# PROCESS
# ---------------------------------------------------------------------------

@dataclass
class ProcessInfo:
    """Information about a running Convexity process."""

    pid: int
    command: str
    started_at: float
    process: subprocess.Popen = field(repr=False)

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    @property
    def return_code(self) -> Optional[int]:
        return self.process.poll()


class ProcessManager:
    """
    Tracks processes started by Convexity.

    This provides the foundation for commands such as:

        jobs
        ps
        kill
        stop
        background execution
    """

    def __init__(self) -> None:
        self._processes: Dict[int, ProcessInfo] = {}
        self._lock = threading.Lock()

    def register(
        self,
        process: subprocess.Popen,
        command: str,
    ) -> ProcessInfo:
        info = ProcessInfo(
            pid=process.pid,
            command=command,
            started_at=time.time(),
            process=process,
        )

        with self._lock:
            self._processes[process.pid] = info

        return info

    def get(self, pid: int) -> Optional[ProcessInfo]:
        with self._lock:
            return self._processes.get(pid)

    def list(self) -> List[ProcessInfo]:
        with self._lock:
            return list(self._processes.values())

    def remove_finished(self) -> None:
        with self._lock:
            finished = [
                pid
                for pid, info in self._processes.items()
                if not info.running
            ]

            for pid in finished:
                self._processes.pop(pid, None)

    def terminate(self, pid: int) -> bool:
        info = self.get(pid)

        if info is None:
            return False

        if not info.running:
            return True

        try:
            info.process.terminate()
            return True
        except OSError:
            return False

    def kill(self, pid: int) -> bool:
        info = self.get(pid)

        if info is None:
            return False

        if not info.running:
            return True

        try:
            info.process.kill()
            return True
        except OSError:
            return False


process_manager = ProcessManager()


# ---------------------------------------------------------------------------
# EXECUTOR
# ---------------------------------------------------------------------------

class CommandExecutor:
    """Main Convexity command execution engine."""

    def __init__(self) -> None:
        self.process_manager = process_manager

    def execute(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
        source: str = "human",
        confirmed: bool = False,
        timeout: Optional[int] = None,
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
            analysis = check_command(
                command,
                source=source,
            )

            # Maple commands remain permission-controlled.
            if source.lower() == "maple" and not confirmed:
                if config.MAPLE_REQUIRE_PERMISSION:
                    raise PermissionDenied(
                        "Maple requires permission before execution."
                    )

            tokens = [analysis.executable] + analysis.arguments

            # IMPORTANT:
            # Do not pass the entire host environment by default.
            env = filter_environment(environment)

            if cwd is not None:
                cwd = os.path.abspath(os.path.expanduser(cwd))

                if not os.path.isdir(cwd):
                    return ExecutionResult(
                        success=False,
                        stderr=f"Working directory does not exist: {cwd}",
                        return_code=1,
                        command=command,
                    )

            effective_timeout = (
                timeout
                if timeout is not None
                else config.DEFAULT_TIMEOUT
            )

            process = subprocess.Popen(
                tokens,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
                shell=False,
            )

            info = self.process_manager.register(
                process,
                command,
            )

            try:
                stdout, stderr = process.communicate(
                    timeout=effective_timeout
                )

                return_code = process.returncode

            except subprocess.TimeoutExpired:

                self._terminate_process(process)

                stdout, stderr = process.communicate()

                duration = time.monotonic() - start_time

                return ExecutionResult(
                    success=False,
                    stdout=self._limit_output(stdout),
                    stderr=(
                        self._limit_output(stderr)
                        + "\nCommand timed out."
                    ).strip(),
                    return_code=-1,
                    command=command,
                    duration=duration,
                    timed_out=True,
                    pid=info.pid,
                )

            duration = time.monotonic() - start_time

            stdout = self._limit_output(stdout)
            stderr = self._limit_output(stderr)

            return ExecutionResult(
                success=(return_code == 0),
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                command=command,
                duration=duration,
                pid=info.pid,
            )

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

            return ExecutionResult(
                success=False,
                stderr=(
                    f"Command not found: "
                    f"{command.split()[0] if command.split() else command}"
                ),
                return_code=127,
                command=command,
                duration=time.monotonic() - start_time,
            )

        except PermissionError:

            return ExecutionResult(
                success=False,
                stderr="Operating system denied permission to execute command.",
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

    # ------------------------------------------------------------------
    # BACKGROUND
    # ------------------------------------------------------------------

    def start_background(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:

        try:
            analysis = check_command(
                command,
                source=source,
            )

            if source.lower() == "maple":
                if config.MAPLE_REQUIRE_PERMISSION and not confirmed:
                    raise PermissionDenied(
                        "Maple requires permission before starting a process."
                    )

            tokens = [analysis.executable] + analysis.arguments

            env = filter_environment(environment)

            if cwd is not None:
                cwd = os.path.abspath(os.path.expanduser(cwd))

                if not os.path.isdir(cwd):
                    return ExecutionResult(
                        success=False,
                        stderr=f"Working directory does not exist: {cwd}",
                        return_code=1,
                        command=command,
                    )

            process = subprocess.Popen(
                tokens,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
                shell=False,
            )

            info = self.process_manager.register(
                process,
                command,
            )

            return ExecutionResult(
                success=True,
                stdout=f"Process started: PID {info.pid}",
                return_code=0,
                command=command,
                pid=info.pid,
            )

        except (SecurityError, PermissionDenied) as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Permission denied: {exc}",
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
                stderr=f"Unable to start process: {exc}",
                return_code=1,
                command=command,
            )

    # ------------------------------------------------------------------
    # PIPELINES
    # ------------------------------------------------------------------

    def execute_pipeline(
        self,
        commands: List[str],
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:
        """
        Execute a basic pipeline.

        Example:

            command1 | command2 | command3

        Each command is validated before execution.
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

        processes: List[subprocess.Popen] = []

        try:
            parsed_commands = []

            for command in commands:
                analysis = check_command(
                    command.strip(),
                    source=source,
                )

                parsed_commands.append(
                    [analysis.executable] + analysis.arguments
                )

            previous_stdout = None

            for index, args in enumerate(parsed_commands):

                process = subprocess.Popen(
                    args,
                    cwd=cwd,
                    env=filter_environment(),
                    stdin=previous_stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    universal_newlines=True,
                    shell=False,
                )

                processes.append(process)

                if previous_stdout is not None:
                    previous_stdout.close()

                previous_stdout = process.stdout

            final_process = processes[-1]

            stdout, stderr = final_process.communicate(
                timeout=config.DEFAULT_TIMEOUT
            )

            # Make sure earlier processes have finished.
            for process in processes[:-1]:
                process.wait(timeout=config.DEFAULT_TIMEOUT)

            return_code = final_process.returncode

            return ExecutionResult(
                success=(return_code == 0),
                stdout=self._limit_output(stdout),
                stderr=self._limit_output(stderr),
                return_code=return_code,
                command=" | ".join(commands),
            )

        except subprocess.TimeoutExpired:

            for process in processes:
                self._terminate_process(process)

            return ExecutionResult(
                success=False,
                stderr="Pipeline timed out.",
                return_code=-1,
                command=" | ".join(commands),
                timed_out=True,
            )

        except Exception as exc:

            for process in processes:
                self._terminate_process(process)

            return ExecutionResult(
                success=False,
                stderr=f"Pipeline error: {exc}",
                return_code=1,
                command=" | ".join(commands),
            )

    # ------------------------------------------------------------------
    # SHELL SEGMENTS
    # ------------------------------------------------------------------

    def execute_shell_segments(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:
        """
        Prepare a command containing shell operators.

        The full shell grammar will eventually live in the Convexity shell
        parser. For now this safely recognizes pipeline segments and refuses
        to silently interpret unsupported operators.
        """

        segments = split_shell_segments(command)

        if not segments:
            return ExecutionResult(
                success=False,
                stderr="Empty command.",
                return_code=1,
                command=command,
            )

        # Pure pipeline.
        if "|" in segments:

            if any(
                operator in segments
                for operator in ("&&", "||", ";", ">", ">>", "<")
            ):
                return ExecutionResult(
                    success=False,
                    stderr=(
                        "Mixed shell operators are not yet handled by "
                        "the Convexity shell engine."
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

        # Unsupported operators.
        operators = {
            "&&",
            "||",
            ";",
            ">",
            ">>",
            "<",
        }

        if any(segment in operators for segment in segments):
            return ExecutionResult(
                success=False,
                stderr=(
                    "This shell operator requires the Convexity shell "
                    "parser and redirection engine."
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

    # ------------------------------------------------------------------
    # PROCESS CONTROL
    # ------------------------------------------------------------------

    def terminate(self, pid: int) -> bool:
        return self.process_manager.terminate(pid)

    def kill(self, pid: int) -> bool:
        return self.process_manager.kill(pid)

    def list_processes(self) -> List[ProcessInfo]:
        self.process_manager.remove_finished()
        return self.process_manager.list()

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    @staticmethod
    def _limit_output(value: Optional[str]) -> str:

        if not value:
            return ""

        maximum = config.MAX_OUTPUT_LENGTH

        if len(value) <= maximum:
            return value

        return (
            value[:maximum]
            + "\n\n[Output truncated by Convexity]"
        )

    @staticmethod
    def _terminate_process(
        process: subprocess.Popen,
    ) -> None:

        if process.poll() is not None:
            return

        try:
            process.terminate()

            try:
                process.wait(timeout=2)
                return
            except subprocess.TimeoutExpired:
                pass

        except OSError:
            pass

        try:
            process.kill()
        except OSError:
            pass


# -------------------------------
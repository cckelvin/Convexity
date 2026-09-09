"""
Convexity Terminal Runtime
Version: 1.1.0

Central coordinator for the Convexity terminal.

Responsibilities:
- Manage independent terminal sessions
- Build execution contexts
- Connect sessions to the command executor
- Execute foreground commands
- Start background commands
- Track runtime statistics
- Record command history
- Maintain per-session output state

This module does NOT contain:
- AI/model logic
- Maple reasoning
- Memory systems
- Chat logic
- Model loading
- Provider logic

Those belong to maple/ and model/.

Architecture:

    User / Maple
         |
         v
      Runtime
         |
         +---- Session
         |
         +---- Executor
                  |
                  v
             ProcessManager
                  |
                  v
             Operating System
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from .executor import CommandExecutor, ExecutionResult
from .session import (
    SessionManager,
    TerminalSession,
    get_session_manager,
)


__version__ = "1.1.0"


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RuntimeErrorBase(Exception):
    """Base exception for Convexity runtime errors."""


class RuntimeClosedError(RuntimeErrorBase):
    """Raised when an operation is attempted on a closed runtime."""


class RuntimeExecutionError(RuntimeErrorBase):
    """Raised when a runtime operation cannot be completed."""


# ============================================================================
# EXECUTION CONTEXT
# ============================================================================

@dataclass
class ExecutionContext:
    """
    Snapshot of the session state used for command execution.

    The context is intentionally a snapshot. A command receives the
    session's cwd and environment without modifying global Python state.
    """

    session_id: str
    cwd: str
    environment: dict[str, str]
    columns: int
    rows: int
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cwd": self.cwd,
            "environment": dict(self.environment),
            "columns": self.columns,
            "rows": self.rows,
            "created_at": self.created_at,
        }


# ============================================================================
# RUNTIME STATISTICS
# ============================================================================

@dataclass
class RuntimeStats:
    """Runtime-level execution statistics."""

    started_at: float

    commands_executed: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    background_commands: int = 0
    active_sessions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "uptime": max(
                0.0,
                time.time() - self.started_at,
            ),
            "commands_executed": self.commands_executed,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "background_commands": self.background_commands,
            "active_sessions": self.active_sessions,
        }


# ============================================================================
# TERMINAL RUNTIME
# ============================================================================

class TerminalRuntime:
    """
    Central coordinator for Convexity Terminal.

    Runtime does not execute operating-system processes itself.

    It coordinates:

        Session
           |
           v
        Context
           |
           v
        Executor
           |
           v
        ProcessManager
           |
           v
        Operating System

    Each TerminalSession owns its own cwd, environment, history,
    aliases, Maple state and active-job information.
    """

    def __init__(
        self,
        *,
        session_manager: Optional[SessionManager] = None,
        executor: Optional[CommandExecutor] = None,
    ) -> None:

        self.session_manager = (
            session_manager
            if session_manager is not None
            else get_session_manager()
        )

        self.executor = (
            executor
            if executor is not None
            else CommandExecutor()
        )

        self.started_at = time.time()
        self.closed = False

        self.stats = RuntimeStats(
            started_at=self.started_at,
        )

        self._refresh_session_count()

    # ========================================================================
    # INTERNAL
    # ========================================================================

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeClosedError(
                "Convexity Terminal Runtime is closed."
            )

    def _refresh_session_count(self) -> None:
        try:
            self.stats.active_sessions = len(
                self.session_manager.list_sessions()
            )
        except Exception:
            self.stats.active_sessions = 0

    @staticmethod
    def _result_output(result: ExecutionResult) -> str:
        """
        Combine stdout/stderr into the session's last-output state.
        """

        parts: list[str] = []

        if result.stdout:
            parts.append(result.stdout)

        if result.stderr:
            parts.append(result.stderr)

        return "\n".join(parts)

    def _record_result(
        self,
        session: TerminalSession,
        command: str,
        result: ExecutionResult,
        *,
        source: str,
        duration: Optional[float],
    ) -> None:
        """
        Update session state and runtime statistics.

        History uses the actual TerminalSession API and therefore does
        not attempt to store stdout/stderr inside HistoryEntry.
        """

        self.stats.commands_executed += 1

        if result.success:
            self.stats.successful_commands += 1
        else:
            self.stats.failed_commands += 1

        output = self._result_output(result)

        try:
            session.set_last_output(output)
        except Exception:
            pass

        try:
            session.add_history(
                command=command,
                exit_code=result.return_code,
                duration=duration,
                source=source,
            )
        except Exception:
            # History must never break command execution.
            pass

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def close(self) -> None:
        """
        Close the runtime and all managed sessions.
        """

        if self.closed:
            return

        try:
            self.session_manager.close_all()
        finally:
            self.closed = True
            self.stats.active_sessions = 0

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

    def create_session(
        self,
        *,
        session_id: Optional[str] = None,
    ) -> TerminalSession:
        """
        Create a new independent terminal session.

        Each session has its own cwd and environment state.
        """

        self._ensure_open()

        if session_id is None:
            session = self.session_manager.create_session()
        else:
            session = self.session_manager.create_session(
                session_id=session_id,
            )

        self._refresh_session_count()

        return session

    def get_session(
        self,
        session_id: str,
    ) -> TerminalSession:
        """
        Retrieve a session by ID.
        """

        self._ensure_open()

        session = self.session_manager.get_session(
            session_id
        )

        if session is None:
            raise RuntimeExecutionError(
                f"Session not found: {session_id}"
            )

        return session

    def remove_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Remove a terminal session.
        """

        self._ensure_open()

        removed = self.session_manager.remove_session(
            session_id
        )

        self._refresh_session_count()

        return removed

    def list_sessions(self) -> list[Any]:
        """
        Return currently managed sessions.
        """

        self._ensure_open()

        sessions = self.session_manager.list_sessions()

        self.stats.active_sessions = len(sessions)

        return sessions

    # ========================================================================
    # CONTEXT
    # ========================================================================

    def get_context(
        self,
        session_id: str,
    ) -> ExecutionContext:
        """
        Build an execution context from a terminal session.

        No global os.chdir() is performed.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        return ExecutionContext(
            session_id=session.session_id,
            cwd=session.cwd,
            environment=session.export_environment(),
            columns=session.columns,
            rows=session.rows,
            created_at=time.time(),
        )

    # ========================================================================
    # FOREGROUND EXECUTION
    # ========================================================================

    def execute(
        self,
        session_id: str,
        command: str,
        *,
        source: str = "human",
        confirmed: bool = False,
        timeout: Optional[float] = None,
        interactive: bool = False,
        callback=None,
    ) -> ExecutionResult:
        """
        Execute a foreground command.

        source may be:

            human
            maple
            system
            flow

        Maple approval is handled by the executor/security layer.

        Human commands are not subject to Maple approval.
        """

        self._ensure_open()

        if not command or not command.strip():
            raise ValueError(
                "Command cannot be empty."
            )

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        started = time.monotonic()

        try:
            if interactive:
                result = self.executor.execute_interactive(
                    command,
                    cwd=context.cwd,
                    environment=context.environment,
                    source=source,
                    confirmed=confirmed,
                    callback=callback,
                )
            else:
                result = self.executor.execute(
                    command,
                    cwd=context.cwd,
                    environment=context.environment,
                    source=source,
                    confirmed=confirmed,
                    timeout=timeout,
                    callback=callback,
                )

        except Exception:
            duration = time.monotonic() - started

            self.stats.commands_executed += 1
            self.stats.failed_commands += 1

            try:
                session.add_history(
                    command=command,
                    exit_code=1,
                    duration=duration,
                    source=source,
                )
            except Exception:
                pass

            raise

        duration = time.monotonic() - started

        self._record_result(
            session,
            command,
            result,
            source=source,
            duration=duration,
        )

        return result

    # ========================================================================
    # BACKGROUND EXECUTION
    # ========================================================================

    def execute_background(
        self,
        session_id: str,
        command: str,
        *,
        source: str = "human",
        confirmed: bool = False,
        interactive: bool = False,
        callback=None,
    ) -> ExecutionResult:
        """
        Start a command in the background.

        The canonical ProcessManager remains responsible for the
        actual process lifecycle.
        """

        self._ensure_open()

        if not command or not command.strip():
            raise ValueError(
                "Command cannot be empty."
            )

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        started = time.monotonic()

        try:
            result = self.executor.start_background(
                command,
                cwd=context.cwd,
                environment=context.environment,
                source=source,
                confirmed=confirmed,
                interactive=interactive,
                callback=callback,
            )

        except Exception:
            duration = time.monotonic() - started

            self.stats.commands_executed += 1
            self.stats.failed_commands += 1

            try:
                session.add_history(
                    command=command,
                    exit_code=1,
                    duration=duration,
                    source=source,
                )
            except Exception:
                pass

            raise

        duration = time.monotonic() - started

        self.stats.commands_executed += 1
        self.stats.background_commands += 1

        if result.success:
            self.stats.successful_commands += 1
        else:
            self.stats.failed_commands += 1

        try:
            session.set_last_output(
                self._result_output(result)
            )
        except Exception:
            pass

        # Register the canonical process ID with this session.
        if result.process_id is not None:
            try:
                session.register_job(
                    result.process_id
                )
            except Exception:
                pass

        try:
            session.add_history(
                command=command,
                exit_code=(
                    result.return_code
                    if not result.success
                    else None
                ),
                duration=duration,
                source=source,
            )
        except Exception:
            pass

        return result

    # ========================================================================
    # SHELL EXECUTION
    # ========================================================================

    def execute_shell(
        self,
        session_id: str,
        command: str,
        *,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:
        """
        Execute a shell expression through the canonical executor.

        This keeps shell parsing/execution out of the runtime itself.
        """

        self._ensure_open()

        if not command or not command.strip():
            raise ValueError(
                "Command cannot be empty."
            )

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        started = time.monotonic()

        try:
            result = self.executor.execute_shell_segments(
                command,
                cwd=context.cwd,
                source=source,
                confirmed=confirmed,
            )

        except Exception:
            duration = time.monotonic() - started

            self.stats.commands_executed += 1
            self.stats.failed_commands += 1

            try:
                session.add_history(
                    command=command,
                    exit_code=1,
                    duration=duration,
                    source=source,
                )
            except Exception:
                pass

            raise

        duration = time.monotonic() - started

        self._record_result(
            session,
            command,
            result,
            source=source,
            duration=duration,
        )

        return result

    # ========================================================================
    # PIPELINE
    # ========================================================================

    def execute_pipeline(
        self,
        session_id: str,
        commands: list[str],
        *,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:
        """
        Execute a command pipeline through the executor.

        The runtime does not create pipeline subprocesses itself.
        """

        self._ensure_open()

        if not commands:
            raise ValueError(
                "Pipeline cannot be empty."
            )

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        started = time.monotonic()

        result = self.executor.execute_pipeline(
            commands,
            cwd=context.cwd,
            source=source,
            confirmed=confirmed,
        )

        duration = time.monotonic() - started

        command_text = " | ".join(commands)

        self._record_result(
            session,
            command_text,
            result,
            source=source,
            duration=duration,
        )

        return result

    # ========================================================================
    # SESSION OUTPUT
    # ========================================================================

    def get_last_output(
        self,
        session_id: str,
    ) -> str:
        """
        Return the last output generated by a session.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        return session.get_last_output()

    def set_last_output(
        self,
        session_id: str,
        output: str,
    ) -> None:
        """
        Set the session's last-output buffer.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        session.set_last_output(output)

    # ========================================================================
    # MAPLE STATE
    # ========================================================================

    def maple_loaded(
        self,
        session_id: str,
    ) -> bool:
        """
        Return whether Maple is currently loaded for a session.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        return session.is_maple_loaded()

    def load_maple(
        self,
        session_id: str,
        *,
        maple_session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Activate Maple for a terminal session.

        Maple does not replace the terminal.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        session.load_maple(
            maple_session_id=maple_session_id,
            metadata=metadata,
        )

    def kill_maple(
        self,
        session_id: str,
    ) -> None:
        """
        Deactivate Maple without destroying terminal state.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        session.kill_maple()

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> RuntimeStats:
        """
        Return current runtime statistics.
        """

        self._ensure_open()

        self._refresh_session_count()

        return self.stats

    def stats_dict(self) -> dict[str, Any]:
        """
        Return runtime statistics as a dictionary.
        """

        return self.get_stats().to_dict()

    # ========================================================================
    # SESSION SNAPSHOT
    # ========================================================================

    def snapshot(
        self,
        session_id: str,
        *,
        include_environment: bool = False,
    ) -> dict[str, Any]:
        """
        Return a diagnostic snapshot of the runtime and session.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        return {
            "runtime": self.stats_dict(),
            "session": session.snapshot(
                include_environment=include_environment
            ),
        }


# ============================================================================
# DEFAULT RUNTIME
# ============================================================================

_default_runtime: Optional[TerminalRuntime] = None


def get_runtime() -> TerminalRuntime:
    """
    Return the default Convexity runtime.

    A new runtime is created automatically after the previous one
    has been closed.
    """

    global _default_runtime

    if (
        _default_runtime is None
        or _default_runtime.closed
    ):
        _default_runtime = TerminalRuntime()

    return _default_runtime


def close_runtime() -> None:
    """
    Close and discard the default runtime.
    """

    global _default_runtime

    if _default_runtime is not None:
        _default_runtime.close()
        _default_runtime = None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def execute_command(
    session_id: str,
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
    timeout: Optional[float] = None,
    interactive: bool = False,
    callback=None,
) -> ExecutionResult:
    """
    Convenience wrapper around TerminalRuntime.execute().
    """

    return get_runtime().execute(
        session_id,
        command,
        source=source,
        confirmed=confirmed,
        timeout=timeout,
        interactive=interactive,
        callback=callback,
    )


def execute_background(
    session_id: str,
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
    interactive: bool = False,
    callback=None,
) -> ExecutionResult:
    """
    Convenience wrapper around TerminalRuntime.execute_background().
    """

    return get_runtime().execute_background(
        session_id,
        command,
        source=source,
        confirmed=confirmed,
        interactive=interactive,
        callback=callback,
    )


def execute_shell(
    session_id: str,
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
) -> ExecutionResult:
    """
    Convenience wrapper around TerminalRuntime.execute_shell().
    """

    return get_runtime().execute_shell(
        session_id,
        command,
        source=source,
        confirmed=confirmed,
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ExecutionContext",
    "RuntimeStats",
    "RuntimeErrorBase",
    "RuntimeClosedError",
    "RuntimeExecutionError",
    "TerminalRuntime",
    "get_runtime",
    "close_runtime",
    "execute_command",
    "execute_background",
    "execute_shell",
]

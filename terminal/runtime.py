"""
Convexity Terminal Runtime
Version: 1.0.1

Central coordinator for Convexity terminal subsystems.

Responsibilities:
- Manage terminal sessions
- Build execution contexts
- Connect sessions to the command executor
- Execute foreground commands
- Start background commands
- Track runtime statistics
- Record command history

This module intentionally does NOT contain:
- AI/model logic
- Maple reasoning
- Memory systems
- Chat logic
- Model loading
- Provider logic

Those belong to maple/ and model/.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from .session import (
    TerminalSession,
    SessionManager,
    get_session_manager,
)
from .executor import CommandExecutor


__version__ = "1.0.1"


# ============================================================
# EXCEPTIONS
# ============================================================

class RuntimeErrorBase(Exception):
    """Base exception for Convexity runtime errors."""


class RuntimeClosedError(RuntimeErrorBase):
    """Raised when an operation is attempted on a closed runtime."""


class RuntimeExecutionError(RuntimeErrorBase):
    """Raised when runtime execution fails unexpectedly."""


# ============================================================
# EXECUTION CONTEXT
# ============================================================

@dataclass
class ExecutionContext:
    """
    Snapshot of the environment in which a command executes.
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


# ============================================================
# RUNTIME STATISTICS
# ============================================================

@dataclass
class RuntimeStats:
    """
    Runtime-level statistics.
    """

    started_at: float
    commands_executed: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    background_commands: int = 0
    active_sessions: int = 0

    def to_dict(self) -> dict[str, Any]:
        uptime = max(0.0, time.time() - self.started_at)

        return {
            "started_at": self.started_at,
            "uptime": uptime,
            "commands_executed": self.commands_executed,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "background_commands": self.background_commands,
            "active_sessions": self.active_sessions,
        }


# ============================================================
# TERMINAL RUNTIME
# ============================================================

class TerminalRuntime:
    """
    Central runtime coordinator for Convexity Terminal.

    The runtime connects:

        Session
            ↓
        Execution Context
            ↓
        Command Executor
            ↓
        Operating System
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
            active_sessions=0,
        )

    # ========================================================
    # LIFECYCLE
    # ========================================================

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeClosedError(
                "Convexity Terminal Runtime is closed."
            )

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

    # ========================================================
    # SESSION MANAGEMENT
    # ========================================================

    def create_session(
        self,
        *,
        session_id: Optional[str] = None,
    ) -> TerminalSession:
        """
        Create a new independent terminal session.
        """

        self._ensure_open()

        if session_id:
            session = self.session_manager.create_session(
                session_id=session_id
            )
        else:
            session = self.session_manager.create_session()

        self.stats.active_sessions = len(
            self.session_manager.list_sessions()
        )

        return session

    def get_session(
        self,
        session_id: str,
    ) -> TerminalSession:
        """
        Retrieve a terminal session.
        """

        self._ensure_open()

        session = self.session_manager.get_session(session_id)

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

        self.stats.active_sessions = len(
            self.session_manager.list_sessions()
        )

        return removed

    def list_sessions(self) -> list[Any]:
        """
        Return all active sessions.
        """

        self._ensure_open()

        sessions = self.session_manager.list_sessions()

        self.stats.active_sessions = len(sessions)

        return sessions

    # ========================================================
    # CONTEXT
    # ========================================================

    def get_context(
        self,
        session_id: str,
    ) -> ExecutionContext:
        """
        Build an execution context from a session.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        return ExecutionContext(
            session_id=session.session_id,
            cwd=session.cwd,
            environment=dict(session.environment),
            columns=session.columns,
            rows=session.rows,
            created_at=time.time(),
        )

    # ========================================================
    # FOREGROUND EXECUTION
    # ========================================================

    def execute(
        self,
        session_id: str,
        command: str,
        *,
        source: str = "human",
        confirmed: bool = False,
        timeout: Optional[int] = None,
    ):
        """
        Execute a foreground command.

        source:
            human
            maple
            system
            flow

        confirmed:
            Used when an authorized Maple operation has
            already received confirmation.
        """

        self._ensure_open()

        if not command or not command.strip():
            raise ValueError("Command cannot be empty.")

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        started = time.time()

        try:
            result = self.executor.execute(
                command,
                cwd=context.cwd,
                environment=context.environment,
                source=source,
                confirmed=confirmed,
                timeout=timeout,
            )

        except Exception:
            self.stats.failed_commands += 1

            raise

        finally:
            self.stats.commands_executed += 1

        duration = time.time() - started

        if result.success:
            self.stats.successful_commands += 1
        else:
            self.stats.failed_commands += 1

        # ----------------------------------------------------
        # History
        # ----------------------------------------------------

        try:
            session.add_history(
                command=command,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.return_code,
                source=source,
                duration=duration,
            )
        except (AttributeError, TypeError):
            # History support should never prevent command
            # execution from succeeding.
            pass

        return result

    # ========================================================
    # BACKGROUND EXECUTION
    # ========================================================

    def execute_background(
        self,
        session_id: str,
        command: str,
        *,
        source: str = "human",
        confirmed: bool = False,
    ):
        """
        Start a command in the background.
        """

        self._ensure_open()

        if not command or not command.strip():
            raise ValueError("Command cannot be empty.")

        session = self.get_session(session_id)
        context = self.get_context(session_id)

        try:
            result = self.executor.start_background(
                command,
                cwd=context.cwd,
                environment=context.environment,
                source=source,
                confirmed=confirmed,
            )

        except Exception:
            self.stats.failed_commands += 1
            raise

        self.stats.commands_executed += 1
        self.stats.background_commands += 1

        if result.success:
            self.stats.successful_commands += 1
        else:
            self.stats.failed_commands += 1

        # Register the process with the session.
        if getattr(result, "pid", None) is not None:
            try:
                session.add_job(result.pid)
            except (AttributeError, TypeError):
                pass

        # Record history.
        try:
            session.add_history(
                command=command,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.return_code,
                source=source,
                duration=0.0,
            )
        except (AttributeError, TypeError):
            pass

        return result

    # ========================================================
    # STATISTICS
    # ========================================================

    def get_stats(self) -> RuntimeStats:
        """
        Return current runtime statistics.
        """

        self._ensure_open()

        self.stats.active_sessions = len(
            self.session_manager.list_sessions()
        )

        return self.stats

    def stats_dict(self) -> dict[str, Any]:
        """
        Return runtime statistics as a dictionary.
        """

        return self.get_stats().to_dict()

    # ========================================================
    # SESSION SNAPSHOT
    # ========================================================

    def snapshot(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Return a diagnostic snapshot of a session.
        """

        self._ensure_open()

        session = self.get_session(session_id)

        try:
            session_snapshot = session.snapshot()
        except AttributeError:
            session_snapshot = {
                "session_id": session.session_id,
                "cwd": session.cwd,
                "environment": dict(session.environment),
                "maple_loaded": session.is_maple_loaded(),
            }

        return {
            "runtime": self.stats_dict(),
            "session": session_snapshot,
        }


# ============================================================
# DEFAULT RUNTIME
# ============================================================

_default_runtime: Optional[TerminalRuntime] = None


def get_runtime() -> TerminalRuntime:
    """
    Return the process-wide default Convexity runtime.
    """

    global _default_runtime

    if _default_runtime is None or _default_runtime.closed:
        _default_runtime = TerminalRuntime()

    return _default_runtime


def close_runtime() -> None:
    """
    Close the default runtime.
    """

    global _default_runtime

    if _default_runtime is not None:
        _default_runtime.close()
        _default_runtime = None


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def execute_command(
    session_id: str,
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
    timeout: Optional[int] = None,
):
    """
    Convenience wrapper around TerminalRuntime.execute().
    """

    return get_runtime().execute(
        session_id,
        command,
        source=source,
        confirmed=confirmed,
        timeout=timeout,
    )


def execute_background(
    session_id: str,
    command: str,
    *,
    source: str = "human",
    confirmed: bool = False,
):
    """
    Convenience wrapper around TerminalRuntime.execute_background().
    """

    return get_runtime().execute_background(
        session_id,
        command,
        source=source,
        confirmed=confirmed,
    )


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
]
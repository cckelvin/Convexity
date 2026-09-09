"""
Convexity Terminal Runtime
Version: 1.0.0

Coordinates the low-level terminal subsystems.

This module is intentionally NOT:
- an AI system
- a model loader
- a memory system
- a chat system
- a Maple reasoning engine

Those belong in their respective top-level systems.

Responsibilities:
- Create/manage terminal sessions.
- Build execution contexts.
- Pass session cwd/environment to processes.
- Track runtime state.
- Provide a clean integration layer between terminal.py,
  process.py, executor.py, shell.py and session.py.
"""

from __future__ import annotations

import time

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from .session import (
    TerminalSession,
    SessionManager,
    get_session_manager,
)

try:
    from .executor import (
        CommandExecutor,
        ExecutionResult,
    )
except ImportError:
    CommandExecutor = None
    ExecutionResult = Any


__version__ = "1.0.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RuntimeErrorBase(Exception):
    """Base Convexity runtime error."""


class RuntimeClosedError(RuntimeErrorBase):
    """Raised when the runtime is closed."""


class RuntimeExecutionError(RuntimeErrorBase):
    """Raised when runtime execution cannot be performed."""


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """
    Immutable-ish snapshot of the environment required to execute
    a command for a particular session.

    This prevents process execution from depending on global cwd
    or global environment state.
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
            "environment": dict(
                self.environment
            ),
            "columns": self.columns,
            "rows": self.rows,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Runtime statistics
# ---------------------------------------------------------------------------

@dataclass
class RuntimeStats:
    """Basic runtime statistics."""

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
            "commands_executed": (
                self.commands_executed
            ),
            "successful_commands": (
                self.successful_commands
            ),
            "failed_commands": (
                self.failed_commands
            ),
            "background_commands": (
                self.background_commands
            ),
            "active_sessions": (
                self.active_sessions
            ),
        }


# ---------------------------------------------------------------------------
# Terminal Runtime
# ---------------------------------------------------------------------------

class TerminalRuntime:
    """
    Central runtime coordinator for Convexity's terminal subsystem.

    The runtime owns sessions and connects them to the command
    execution layer.

    It deliberately does not implement:
    - AI
    - model inference
    - memory
    - conversations
    - Maple reasoning
    """

    def __init__(
        self,
        *,
        session_manager: Optional[
            SessionManager
        ] = None,
        executor: Optional[
            CommandExecutor
        ] = None,
    ):

        self.session_manager = (
            session_manager
            or get_session_manager()
        )

        self.executor = executor

        self.started_at = time.time()

        self.closed = False

        self.stats = RuntimeStats(
            started_at=self.started_at
        )

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def _ensure_open(self) -> None:

        if self.closed:
            raise RuntimeClosedError(
                "Convexity terminal runtime is closed."
            )

    def close(self) -> None:

        if self.closed:
            return

        self.session_manager.close_all()

        self.closed = True

        self.stats.active_sessions = 0

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------

    def create_session(
        self,
        *,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        columns: int = 120,
        rows: int = 30,
        history_limit: int = 1000,
    ) -> TerminalSession:

        self._ensure_open()

        session = self.session_manager.create(
            cwd=cwd,
            env=env,
            columns=columns,
            rows=rows,
            history_limit=history_limit,
        )

        self._update_session_stats()

        return session

    def get_session(
        self,
        session_id: str,
    ) -> TerminalSession:

        self._ensure_open()

        return self.session_manager.get(
            session_id
        )

    def remove_session(
        self,
        session_id: str,
    ) -> bool:

        self._ensure_open()

        result = self.session_manager.remove(
            session_id
        )

        self._update_session_stats()

        return result

    def list_sessions(
        self,
    ) -> list[TerminalSession]:

        self._ensure_open()

        return self.session_manager.list()

    def _update_session_stats(self) -> None:

        self.stats.active_sessions = (
            self.session_manager.count()
        )

    # -----------------------------------------------------------------------
    # Context
    # -----------------------------------------------------------------------

    def create_context(
        self,
        session: TerminalSession,
    ) -> ExecutionContext:

        self._ensure_open()

        if session.closed:
            raise RuntimeExecutionError(
                "Cannot create context from "
                "a closed session."
            )

        return ExecutionContext(
            session_id=session.session_id,
            cwd=session.cwd,
            environment=session.export_environment(),
            columns=session.columns,
            rows=session.rows,
            created_at=time.time(),
        )

    def context_for(
        self,
        session_id: str,
    ) -> ExecutionContext:

        session = self.get_session(
            session_id
        )

        return self.create_context(
            session
        )

    # -----------------------------------------------------------------------
    # Executor integration
    # -----------------------------------------------------------------------

    def set_executor(
        self,
        executor: CommandExecutor,
    ) -> None:

        self._ensure_open()

        self.executor = executor

    def _require_executor(self):

        if self.executor is None:

            raise RuntimeExecutionError(
                "No CommandExecutor is attached "
                "to the terminal runtime."
            )

        return self.executor

    # -----------------------------------------------------------------------
    # Command execution
    # -----------------------------------------------------------------------

    def execute(
        self,
        session: TerminalSession,
        command: str | Sequence[str],
        *,
        timeout: Optional[float] = None,
        capture_output: bool = True,
        check: bool = False,
        source: str = "user",
        **kwargs,
    ):
        """
        Execute a command using the session's context.

        The exact execution implementation remains in executor.py.

        This method's job is to provide:
        - session cwd
        - session environment
        - history
        - runtime statistics
        """

        self._ensure_open()

        if session.closed:
            raise RuntimeExecutionError(
                "Cannot execute using a closed session."
            )

        executor = self._require_executor()

        context = self.create_context(
            session
        )

        started = time.time()

        self.stats.commands_executed += 1

        try:

            result = executor.execute(
                command,
                cwd=context.cwd,
                env=context.environment,
                timeout=timeout,
                capture_output=capture_output,
                check=check,
                **kwargs,
            )

        except Exception:

            self.stats.failed_commands += 1

            duration = (
                time.time() - started
            )

            if isinstance(
                command,
                str,
            ):
                command_text = command
            else:
                command_text = " ".join(
                    str(item)
                    for item in command
                )

            session.add_history(
                command_text,
                exit_code=None,
                duration=duration,
                source=source,
            )

            raise

        duration = (
            time.time() - started
        )

        exit_code = getattr(
            result,
            "returncode",
            None,
        )

        if exit_code == 0:

            self.stats.successful_commands += 1

        else:

            self.stats.failed_commands += 1

        if isinstance(
            command,
            str,
        ):
            command_text = command
        else:
            command_text = " ".join(
                str(item)
                for item in command
            )

        session.add_history(
            command_text,
            exit_code=exit_code,
            duration=duration,
            source=source,
        )

        output = getattr(
            result,
            "stdout",
            None,
        )

        if output is not None:
            session.set_last_output(
                str(output)
            )

        return result

    # -----------------------------------------------------------------------
    # Background execution
    # -----------------------------------------------------------------------

    def execute_background(
        self,
        session: TerminalSession,
        command: str | Sequence[str],
        **kwargs,
    ):
        """
        Start a background command.

        Process/job management remains delegated to executor.py.
        """

        self._ensure_open()

        if session.closed:
            raise RuntimeExecutionError(
                "Cannot execute using a closed session."
            )

        executor = self._require_executor()

        context = self.create_context(
            session
        )

        self.stats.commands_executed += 1

        self.stats.background_commands += 1

        result = executor.execute_background(
            command,
            cwd=context.cwd,
            env=context.environment,
            **kwargs,
        )

        return result

    # -----------------------------------------------------------------------
    # Environment helpers
    # -----------------------------------------------------------------------

    def environment(
        self,
        session_id: str,
    ) -> dict[str, str]:

        session = self.get_session(
            session_id
        )

        return session.export_environment()

    def working_directory(
        self,
        session_id: str,
    ) -> str:

        session = self.get_session(
            session_id
        )

        return session.cwd

    # -----------------------------------------------------------------------
    # Runtime state
    # -----------------------------------------------------------------------

    def is_running(self) -> bool:

        return not self.closed

    @property
    def uptime(self) -> float:

        return max(
            0.0,
            time.time() - self.started_at,
        )

    def status(self) -> dict[str, Any]:

        self._update_session_stats()

        return {
            "version": __version__,
            "running": not self.closed,
            "uptime": self.uptime,
            "sessions": self.stats.active_sessions,
            "stats": self.stats.to_dict(),
        }


# ---------------------------------------------------------------------------
# Default runtime
# ---------------------------------------------------------------------------

_default_runtime: Optional[
    TerminalRuntime
] = None


def get_runtime() -> TerminalRuntime:
    """Return the shared Convexity terminal runtime."""

    global _default_runtime

    if _default_runtime is None:
        _default_runtime = TerminalRuntime()

    return _default_runtime


def create_runtime(
    *,
    executor: Optional[
        CommandExecutor
    ] = None,
) -> TerminalRuntime:

    return TerminalRuntime(
        executor=executor
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ExecutionContext",
    "RuntimeStats",
    "TerminalRuntime",
    "RuntimeErrorBase",
    "RuntimeClosedError",
    "RuntimeExecutionError",
    "get_runtime",
    "create_runtime",
]
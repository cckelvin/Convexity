"""
Convexity Terminal Session
Version: 1.0.0

Represents one independent Convexity terminal session.

A session owns:
- Current working directory
- Environment variables
- Aliases
- Command history
- Terminal dimensions
- Maple activation state
- Session metadata

The session does NOT execute commands itself.

Execution belongs to the process/executor layer.

Architecture:

    Convexity
       |
       +---- Session
       |       |
       |       +---- Environment
       |       +---- History
       |       +---- Aliases
       |       +---- Maple state
       |
       +---- Executor
       |
       +---- Process
       |
       +---- PTY
"""

from __future__ import annotations

import os
import platform
import time
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


__version__ = "1.0.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SessionError(Exception):
    """Base session error."""


class SessionClosedError(SessionError):
    """Raised when a closed session is used."""


class SessionPathError(SessionError):
    """Raised when a session path is invalid."""


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

@dataclass
class HistoryEntry:
    """One command history entry."""

    command: str

    timestamp: float = field(
        default_factory=time.time
    )

    exit_code: Optional[int] = None

    duration: Optional[float] = None

    source: str = "user"

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "timestamp": self.timestamp,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TerminalSession:
    """
    Independent Convexity terminal session.

    Important:
    The session's cwd is stored internally.

    It does NOT call os.chdir().

    This allows multiple Convexity sessions to exist
    without changing the process-wide working directory.
    """

    def __init__(
        self,
        *,
        session_id: Optional[str] = None,
        cwd: Optional[str | Path] = None,
        env: Optional[dict[str, str]] = None,
        columns: int = 120,
        rows: int = 30,
        history_limit: int = 1000,
    ):
        self.session_id = (
            session_id
            or uuid.uuid4().hex
        )

        self.created_at = time.time()

        self.closed_at: Optional[float] = None

        self.closed = False

        # ------------------------------------------------------------------
        # Working directory
        # ------------------------------------------------------------------

        if cwd is None:
            cwd = os.getcwd()

        self._cwd = self._resolve_directory(
            cwd
        )

        # ------------------------------------------------------------------
        # Environment
        # ------------------------------------------------------------------

        if env is None:
            self.environment = dict(
                os.environ
            )
        else:
            self.environment = {
                str(key): str(value)
                for key, value in env.items()
            }

        # ------------------------------------------------------------------
        # Aliases
        # ------------------------------------------------------------------

        self.aliases: dict[str, str] = {}

        # ------------------------------------------------------------------
        # History
        # ------------------------------------------------------------------

        self.history: list[
            HistoryEntry
        ] = []

        self.history_limit = max(
            1,
            int(history_limit),
        )

        # ------------------------------------------------------------------
        # Terminal dimensions
        # ------------------------------------------------------------------

        self.columns = max(
            1,
            int(columns),
        )

        self.rows = max(
            1,
            int(rows),
        )

        # ------------------------------------------------------------------
        # Maple state
        # ------------------------------------------------------------------

        self.maple_loaded = False

        self.maple_session_id: Optional[
            str
        ] = None

        self.maple_metadata: dict = {}

        # ------------------------------------------------------------------
        # Runtime state
        # ------------------------------------------------------------------

        self.last_exit_code: Optional[int] = None

        self.last_command: Optional[str] = None

        self.last_output: str = ""

        self.active_jobs: set[int] = set()

        self.metadata: dict = {}

    # -----------------------------------------------------------------------
    # State
    # -----------------------------------------------------------------------

    def _ensure_open(self) -> None:

        if self.closed:
            raise SessionClosedError(
                "Terminal session is closed."
            )

    @property
    def uptime(self) -> float:

        end = (
            self.closed_at
            or time.time()
        )

        return max(
            0.0,
            end - self.created_at,
        )

    # -----------------------------------------------------------------------
    # Working directory
    # -----------------------------------------------------------------------

    @staticmethod
    def _resolve_directory(
        directory: str | Path,
    ) -> Path:

        path = Path(
            directory
        ).expanduser()

        try:
            path = path.resolve()

        except OSError as exc:
            raise SessionPathError(
                f"Unable to resolve path: {directory}"
            ) from exc

        if not path.exists():
            raise SessionPathError(
                f"Directory does not exist: {path}"
            )

        if not path.is_dir():
            raise SessionPathError(
                f"Path is not a directory: {path}"
            )

        return path

    @property
    def cwd(self) -> str:
        """Return the current working directory."""

        return str(self._cwd)

    def get_cwd(self) -> Path:
        """Return the cwd as a Path."""

        return self._cwd

    def change_directory(
        self,
        directory: str | Path,
    ) -> Path:
        """
        Change this session's working directory.

        This does not modify the global Python cwd.
        """

        self._ensure_open()

        directory = Path(
            directory
        ).expanduser()

        if not directory.is_absolute():
            directory = (
                self._cwd / directory
            )

        self._cwd = self._resolve_directory(
            directory
        )

        return self._cwd

    def home_directory(self) -> Path:

        return Path.home().resolve()

    # -----------------------------------------------------------------------
    # Environment
    # -----------------------------------------------------------------------

    def get_env(
        self,
        name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:

        self._ensure_open()

        return self.environment.get(
            name,
            default,
        )

    def set_env(
        self,
        name: str,
        value: str,
    ) -> None:

        self._ensure_open()

        if not name:
            raise ValueError(
                "Environment variable name "
                "cannot be empty."
            )

        self.environment[str(name)] = str(
            value
        )

    def unset_env(
        self,
        name: str,
    ) -> bool:

        self._ensure_open()

        return (
            self.environment.pop(
                name,
                None,
            )
            is not None
        )

    def has_env(
        self,
        name: str,
    ) -> bool:

        self._ensure_open()

        return name in self.environment

    def export_environment(self) -> dict[str, str]:

        self._ensure_open()

        return dict(
            self.environment
        )

    # -----------------------------------------------------------------------
    # Aliases
    # -----------------------------------------------------------------------

    def set_alias(
        self,
        name: str,
        command: str,
    ) -> None:

        self._ensure_open()

        name = name.strip()

        if not name:
            raise ValueError(
                "Alias name cannot be empty."
            )

        if not command.strip():
            raise ValueError(
                "Alias command cannot be empty."
            )

        self.aliases[name] = command

    def get_alias(
        self,
        name: str,
    ) -> Optional[str]:

        self._ensure_open()

        return self.aliases.get(
            name
        )

    def remove_alias(
        self,
        name: str,
    ) -> bool:

        self._ensure_open()

        return (
            self.aliases.pop(
                name,
                None,
            )
            is not None
        )

    def list_aliases(self) -> dict[str, str]:

        self._ensure_open()

        return dict(
            self.aliases
        )

    def expand_alias(
        self,
        command: str,
    ) -> str:

        self._ensure_open()

        stripped = command.lstrip()

        if not stripped:
            return command

        parts = stripped.split(
            maxsplit=1
        )

        alias = self.aliases.get(
            parts[0]
        )

        if alias is None:
            return command

        if len(parts) == 1:
            return alias

        return (
            alias
            + " "
            + parts[1]
        )

    # -----------------------------------------------------------------------
    # History
    # -----------------------------------------------------------------------

    def add_history(
        self,
        command: str,
        *,
        exit_code: Optional[int] = None,
        duration: Optional[float] = None,
        source: str = "user",
    ) -> HistoryEntry:

        self._ensure_open()

        entry = HistoryEntry(
            command=command,
            exit_code=exit_code,
            duration=duration,
            source=source,
        )

        self.history.append(
            entry
        )

        if len(self.history) > self.history_limit:

            self.history = self.history[
                -self.history_limit:
            ]

        self.last_command = command

        self.last_exit_code = exit_code

        return entry

    def get_history(
        self,
        limit: Optional[int] = None,
    ) -> list[HistoryEntry]:

        self._ensure_open()

        entries = list(
            self.history
        )

        if limit is not None:
            entries = entries[
                -max(0, int(limit)):
            ]

        return entries

    def clear_history(self) -> None:

        self._ensure_open()

        self.history.clear()

    def search_history(
        self,
        query: str,
    ) -> list[HistoryEntry]:

        self._ensure_open()

        query = query.lower()

        return [
            entry
            for entry in self.history
            if query in entry.command.lower()
        ]

    # -----------------------------------------------------------------------
    # Maple
    # -----------------------------------------------------------------------

    def load_maple(
        self,
        *,
        maple_session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Activate Maple for this terminal session.

        Loading Maple does not replace the terminal.

        The user can continue normal terminal usage.

        Maple becomes the agent/analysis layer when
        the user asks Maple to perform tasks.
        """

        self._ensure_open()

        self.maple_loaded = True

        self.maple_session_id = (
            maple_session_id
            or uuid.uuid4().hex
        )

        self.maple_metadata = dict(
            metadata or {}
        )

    def kill_maple(self) -> None:
        """
        Deactivate Maple for this session.

        Existing terminal state remains intact.
        """

        self._ensure_open()

        self.maple_loaded = False

        self.maple_session_id = None

        self.maple_metadata.clear()

    def is_maple_loaded(self) -> bool:

        self._ensure_open()

        return self.maple_loaded

    # -----------------------------------------------------------------------
    # Jobs
    # -----------------------------------------------------------------------

    def register_job(
        self,
        job_id: int,
    ) -> None:

        self._ensure_open()

        self.active_jobs.add(
            int(job_id)
        )

    def unregister_job(
        self,
        job_id: int,
    ) -> None:

        self._ensure_open()

        self.active_jobs.discard(
            int(job_id)
        )

    def has_job(
        self,
        job_id: int,
    ) -> bool:

        self._ensure_open()

        return int(job_id) in self.active_jobs

    def list_jobs(self) -> list[int]:

        self._ensure_open()

        return sorted(
            self.active_jobs
        )

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------

    def set_last_output(
        self,
        output: str,
    ) -> None:

        self._ensure_open()

        self.last_output = output

    def get_last_output(self) -> str:

        self._ensure_open()

        return self.last_output

    # -----------------------------------------------------------------------
    # Terminal dimensions
    # -----------------------------------------------------------------------

    def resize(
        self,
        columns: int,
        rows: int,
    ) -> None:

        self._ensure_open()

        columns = int(columns)
        rows = int(rows)

        if columns <= 0 or rows <= 0:
            raise ValueError(
                "Terminal dimensions must be positive."
            )

        self.columns = columns
        self.rows = rows

    # -----------------------------------------------------------------------
    # Platform information
    # -----------------------------------------------------------------------

    def platform_info(self) -> dict:

        self._ensure_open()

        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "os_name": os.name,
        }

    # -----------------------------------------------------------------------
    # Snapshot
    # -----------------------------------------------------------------------

    def snapshot(
        self,
        *,
        include_environment: bool = False,
    ) -> dict:
        """
        Return a serializable snapshot of the session.

        Environment variables are excluded by default
        because they can contain secrets.
        """

        self._ensure_open()

        result = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "uptime": self.uptime,
            "closed": self.closed,
            "cwd": self.cwd,
            "columns": self.columns,
            "rows": self.rows,
            "maple_loaded": self.maple_loaded,
            "maple_session_id": (
                self.maple_session_id
            ),
            "last_command": self.last_command,
            "last_exit_code": self.last_exit_code,
            "active_jobs": self.list_jobs(),
            "aliases": dict(self.aliases),
            "history_count": len(
                self.history
            ),
            "metadata": dict(
                self.metadata
            ),
        }

        if include_environment:
            result["environment"] = (
                dict(self.environment)
            )

        return result

    # -----------------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------------

    def reset(
        self,
        *,
        cwd: Optional[str | Path] = None,
        clear_history: bool = False,
        clear_aliases: bool = False,
    ) -> None:

        self._ensure_open()

        if cwd is not None:
            self._cwd = self._resolve_directory(
                cwd
            )

        self.last_command = None

        self.last_exit_code = None

        self.last_output = ""

        self.active_jobs.clear()

        self.kill_maple()

        if clear_history:
            self.history.clear()

        if clear_aliases:
            self.aliases.clear()

    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------

    def close(self) -> None:

        if self.closed:
            return

        self.closed = True

        self.closed_at = time.time()

        self.maple_loaded = False

        self.maple_session_id = None

        self.active_jobs.clear()

    # -----------------------------------------------------------------------
    # Context manager
    # -----------------------------------------------------------------------

    def __enter__(
        self,
    ) -> "TerminalSession":

        self._ensure_open()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:

        self.close()


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages multiple independent Convexity sessions.
    """

    def __init__(self):

        self._sessions: dict[
            str,
            TerminalSession,
        ] = {}

    def create(
        self,
        *,
        cwd: Optional[str | Path] = None,
        env: Optional[dict[str, str]] = None,
        columns: int = 120,
        rows: int = 30,
        history_limit: int = 1000,
    ) -> TerminalSession:

        session = TerminalSession(
            cwd=cwd,
            env=env,
            columns=columns,
            rows=rows,
            history_limit=history_limit,
        )

        self._sessions[
            session.session_id
        ] = session

        return session

    def get(
        self,
        session_id: str,
    ) -> TerminalSession:

        session = self._sessions.get(
            session_id
        )

        if session is None:
            raise SessionError(
                f"Session not found: {session_id}"
            )

        return session

    def remove(
        self,
        session_id: str,
        *,
        close: bool = True,
    ) -> bool:

        session = self._sessions.pop(
            session_id,
            None,
        )

        if session is None:
            return False

        if close:
            session.close()

        return True

    def lis
"""
Convexity Job Compatibility Layer
Version: 1.0.0

Jobs are a user-facing view over Convexity's canonical process layer.

Canonical process management:
    terminal/process.py

This module exists for:
    jobs
    ps
    job lookup
    job control
    compatibility with older terminal code

It does NOT create subprocesses directly.
"""

from __future__ import annotations

import signal

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .process import (
    ManagedProcess,
    ProcessInfo,
    ProcessManager,
    ProcessState,
    process_manager,
)


__version__ = "1.0.0"


# ============================================================================
# JOB STATE
# ============================================================================

class JobState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"
    KILLED = "killed"
    UNKNOWN = "unknown"


def _map_state(state: ProcessState) -> JobState:
    """
    Convert canonical ProcessState into the legacy JobState API.
    """

    try:
        return JobState(state.value)
    except ValueError:
        return JobState.UNKNOWN


# ============================================================================
# JOB
# ============================================================================

@dataclass
class Job:
    """
    Compatibility representation of a managed Convexity process.
    """

    job_id: int
    pid: int
    command: str

    process: ManagedProcess

    state: JobState = JobState.CREATED

    return_code: Optional[int] = None

    background: bool = False

    started_at: float = 0.0

    finished_at: Optional[float] = None

    cwd: Optional[str] = None

    stdout: str = ""

    stderr: str = ""

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    @property
    def duration(self) -> float:
        return self.process.duration

    def refresh(self) -> JobState:
        """
        Refresh job state from the canonical process.
        """

        self.process.poll()

        info = self.process.info()

        self.state = _map_state(
            info.state
        )

        self.return_code = (
            info.return_code
        )

        self.finished_at = (
            info.finished_at
        )

        self.stdout = (
            self.process.stdout()
        )

        self.stderr = (
            self.process.stderr()
        )

        return self.state


# ============================================================================
# JOB MANAGER
# ============================================================================

class JobManager:
    """
    Compatibility facade around ProcessManager.

    No process creation happens here.
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
    # INTERNAL CONVERSION
    # ========================================================================

    @staticmethod
    def _to_job(
        process: ManagedProcess,
    ) -> Job:

        info = process.info()

        job = Job(
            job_id=info.process_id,
            pid=info.pid,
            command=info.command,
            process=process,
            state=_map_state(
                info.state
            ),
            return_code=info.return_code,
            background=info.background,
            started_at=info.started_at,
            finished_at=info.finished_at,
            cwd=info.cwd,
        )

        job.stdout = process.stdout()
        job.stderr = process.stderr()

        return job

    # ========================================================================
    # GET
    # ========================================================================

    def get(
        self,
        job_id: int,
    ) -> Optional[Job]:

        process = self.process_manager.get(
            job_id
        )

        if process is None:
            return None

        return self._to_job(
            process
        )

    def get_by_pid(
        self,
        pid: int,
    ) -> Optional[Job]:

        processes = self.process_manager.list(
            include_finished=True
        )

        for process in processes:

            info = process.info()

            if info.pid == pid:

                return self._to_job(
                    process
                )

        return None

    # ========================================================================
    # REGISTER
    # ========================================================================

    def register(
        self,
        process,
        command: str,
        *,
        background: bool = False,
        cwd: Optional[str] = None,
    ) -> Job:
        """
        Compatibility method.

        New code should create processes through ProcessManager.
        """

        raise RuntimeError(
            "JobManager.register() no longer accepts raw "
            "subprocess objects. Create the process through "
            "terminal.process.ProcessManager instead."
        )

    # ========================================================================
    # UPDATE
    # ========================================================================

    def update(
        self,
        job: Job,
    ) -> JobState:

        return job.refresh()

    # ========================================================================
    # LIST
    # ========================================================================

    def list_jobs(
        self,
        *,
        include_finished: bool = True,
    ) -> List[Job]:

        processes = self.process_manager.list(
            include_finished=include_finished
        )

        jobs = []

        for process in processes:

            jobs.append(
                self._to_job(
                    process
                )
            )

        return sorted(
            jobs,
            key=lambda item: item.job_id,
        )

    # ========================================================================
    # MONITOR
    # ========================================================================

    def monitor(
        self,
        job: Job,
        *,
        interval: float = 0.25,
    ) -> None:
        """
        ProcessManager already monitors managed processes.

        Kept for compatibility.
        """

        return None

    # ========================================================================
    # WAIT
    # ========================================================================

    def wait(
        self,
        job_id: int,
        timeout: Optional[float] = None,
    ) -> Optional[int]:

        try:

            return self.process_manager.wait(
                job_id,
                timeout=timeout,
            )

        except Exception:
            return None

    # ========================================================================
    # TERMINATE
    # ========================================================================

    def terminate(
        self,
        job_id: int,
    ) -> bool:

        return self.process_manager.terminate(
            job_id
        )

    # ========================================================================
    # KILL
    # ========================================================================

    def kill(
        self,
        job_id: int,
    ) -> bool:

        return self.process_manager.kill(
            job_id
        )

    # ========================================================================
    # SIGNAL
    # ========================================================================

    def send_signal(
        self,
        job_id: int,
        signum: int,
    ) -> bool:

        return self.process_manager.send_signal(
            job_id,
            signum,
        )

    # ========================================================================
    # STOP
    # ========================================================================

    def stop(
        self,
        job_id: int,
    ) -> bool:

        if hasattr(
            self.process_manager,
            "send_signal",
        ):

            return self.process_manager.send_signal(
                job_id,
                signal.SIGSTOP,
            )

        return False

    # ========================================================================
    # CONTINUE
    # ========================================================================

    def continue_job(
        self,
        job_id: int,
    ) -> bool:

        if hasattr(
            self.process_manager,
            "send_signal",
        ):

            return self.process_manager.send_signal(
                job_id,
                signal.SIGCONT,
            )

        return False

    # ========================================================================
    # REMOVE
    # ========================================================================

    def remove(
        self,
        job_id: int,
    ) -> bool:

        process = self.process_manager.get(
            job_id
        )

        if process is None:
            return False

        if process.poll() is None:
            return False

        try:

            return self.process_manager.remove(
                job_id
            )

        except AttributeError:

            return False

    # ========================================================================
    # CLEANUP
    # ========================================================================

    def cleanup_finished(self) -> int:

        return self.process_manager.remove_finished()

    # ========================================================================
    # TERMINATE ALL
    # ========================================================================

    def terminate_all(self) -> int:

        return self.process_manager.terminate_all()


# ============================================================================
# GLOBAL JOB MANAGER
# ============================================================================

job_manager = JobManager()


# ============================================================================
# CONVENIENCE API
# ============================================================================

def get_job(
    job_id: int,
) -> Optional[Job]:

    return job_manager.get(
        job_id
    )


def get_job_by_pid(
    pid: int,
) -> Optional[Job]:

    return job_manager.get_by_pid(
        pid
    )


def list_jobs(
    *,
    include_finished: bool = True,
) -> List[Job]:

    return job_manager.list_jobs(
        include_finished=include_finished
    )


def wait_job(
    job_id: int,
    timeout: Optional[float] = None,
) -> Optional[int]:

    return job_manager.wait(
        job_id,
        timeout
    )


def terminate_job(
    job_id: int,
) -> bool:

    return job_manager.terminate(
        job_id
    )


def kill_job(
    job_id: int,
) -> bool:

    return job_manager.kill(
        job_id
    )


def stop_job(
    job_id: int,
) -> bool:

    return job_manager.stop(
        job_id
    )


def continue_job(
    job_id: int,
) -> bool:

    return job_manager.continue_job(
        job_id
    )


def cleanup_jobs() -> int:

    return job_manager.cleanup_finished()


__all__ = [
    "JobState",
    "Job",
    "JobManager",
    "job_manager",
    "get_job",
    "get_job_by_pid",
    "list_jobs",
    "wait_job",
    "terminate_job",
    "kill_job",
    "stop_job",
    "continue_job",
    "cleanup_jobs",
]

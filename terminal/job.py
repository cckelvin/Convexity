"""
Convexity Process & Job Manager
Version 0.7.0

Provides Convexity-native process/job management.

Responsibilities:
    - register running processes
    - track PIDs
    - foreground/background state
    - process status
    - terminate
    - force kill
    - wait
    - job IDs
    - job listing
    - cleanup finished jobs

This module does not use Bash, PowerShell, CMD, or Termux.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# JOB STATES
# ---------------------------------------------------------------------------

class JobState(str, Enum):

    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"
    KILLED = "killed"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# JOB
# ---------------------------------------------------------------------------

@dataclass
class Job:

    job_id: int

    pid: int

    command: str

    process: subprocess.Popen

    state: JobState = JobState.CREATED

    return_code: Optional[int] = None

    background: bool = False

    started_at: float = field(
        default_factory=time.time
    )

    finished_at: Optional[float] = None

    cwd: Optional[str] = None

    stdout: str = ""

    stderr: str = ""

    lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
    )

    @property
    def running(self) -> bool:

        return self.process.poll() is None

    @property
    def duration(self) -> float:

        end = (
            self.finished_at
            if self.finished_at is not None
            else time.time()
        )

        return end - self.started_at


# ---------------------------------------------------------------------------
# JOB MANAGER
# ---------------------------------------------------------------------------

class JobManager:

    def __init__(self) -> None:

        self._jobs: Dict[int, Job] = {}

        self._next_job_id = 1

        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # REGISTER
    # ------------------------------------------------------------------

    def register(
        self,
        process: subprocess.Popen,
        command: str,
        *,
        background: bool = False,
        cwd: Optional[str] = None,
    ) -> Job:

        with self._lock:

            job = Job(
                job_id=self._next_job_id,
                pid=process.pid,
                command=command,
                process=process,
                state=JobState.RUNNING,
                background=background,
                cwd=cwd,
            )

            self._jobs[
                self._next_job_id
            ] = job

            self._next_job_id += 1

        return job

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def get(
        self,
        job_id: int,
    ) -> Optional[Job]:

        with self._lock:

            return self._jobs.get(
                job_id
            )

    def get_by_pid(
        self,
        pid: int,
    ) -> Optional[Job]:

        with self._lock:

            for job in self._jobs.values():

                if job.pid == pid:
                    return job

        return None

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def update(
        self,
        job: Job,
    ) -> JobState:

        return_code = job.process.poll()

        with job.lock:

            if return_code is None:

                if job.state not in {
                    JobState.STOPPED,
                    JobState.TERMINATED,
                    JobState.KILLED,
                }:

                    job.state = JobState.RUNNING

                return job.state

            job.return_code = return_code

            if job.finished_at is None:

                job.finished_at = time.time()

            if job.state == JobState.TERMINATED:

                return job.state

            if job.state == JobState.KILLED:

                return job.state

            if return_code == 0:

                job.state = JobState.COMPLETED

            else:

                job.state = JobState.FAILED

            return job.state

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def list_jobs(
        self,
        *,
        include_finished: bool = True,
    ) -> List[Job]:

        with self._lock:

            jobs = list(
                self._jobs.values()
            )

        for job in jobs:

            self.update(job)

        if not include_finished:

            jobs = [
                job
                for job in jobs
                if job.running
            ]

        return sorted(
            jobs,
            key=lambda item: item.job_id,
        )

    # ------------------------------------------------------------------
    # START MONITOR
    # ------------------------------------------------------------------

    def monitor(
        self,
        job: Job,
        *,
        interval: float = 0.25,
    ) -> None:

        def worker() -> None:

            while job.process.poll() is None:

                time.sleep(interval)

            self.update(job)

        thread = threading.Thread(
            target=worker,
            daemon=True,
        )

        thread.start()

    # ------------------------------------------------------------------
    # WAIT
    # ------------------------------------------------------------------

    def wait(
        self,
        job_id: int,
        timeout: Optional[float] = None,
    ) -> Optional[int]:

        job = self.get(job_id)

        if job is None:
            return None

        try:

            code = job.process.wait(
                timeout=timeout
            )

        except subprocess.TimeoutExpired:

            return None

        self.update(job)

        return code

    # ------------------------------------------------------------------
    # TERMINATE
    # ------------------------------------------------------------------

    def terminate(
        self,
        job_id: int,
    ) -> bool:

        job = self.get(job_id)

        if job is None:
            return False

        if not job.running:

            self.update(job)

            return True

        try:

            job.process.terminate()

            with job.lock:
                job.state = JobState.TERMINATED

            return True

        except OSError:

            return False

    # ------------------------------------------------------------------
    # KILL
    # ------------------------------------------------------------------

    def kill(
        self,
        job_id: int,
    ) -> bool:

        job = self.get(job_id)

        if job is None:
            return False

        if not job.running:

            self.update(job)

            return True

        try:

            if os.name == "nt":

                job.process.kill()

            else:

                os.kill(
                    job.pid,
                    signal.SIGKILL,
                )

            with job.lock:
                job.state = JobState.KILLED

            return True

        except OSError:

            return False

    # ------------------------------------------------------------------
    # SIGNAL
    # ------------------------------------------------------------------

    def send_signal(
        self,
        job_id: int,
        signum: int,
    ) -> bool:

        job = self.get(job_id)

        if job is None or not job.running:
            return False

        try:

            if os.name == "nt":

                # Windows has a different signal model.
                # CTRL_BREAK_EVENT can be used for console groups,
                # but requires the process to have been started correctly.
                if signum == signal.SIGTERM:

                    job.process.terminate()

                else:

                    job.process.send_signal(
                        signum
                    )

            else:

                os.kill(
                    job.pid,
                    signum,
                )

            return True

        except OSError:

            return False

    # ------------------------------------------------------------------
    # STOP
    # ------------------------------------------------------------------

    def stop(
        self,
        job_id: int,
    ) -> bool:

        job = self.get(job_id)

        if job is None or not job.running:
            return False

        if os.name == "nt":

            # Windows process suspension requires
            # platform-specific APIs. Keep state explicit.
            return False

        try:

            os.kill(
                job.pid,
                signal.SIGSTOP,
            )

            with job.lock:
                job.state = JobState.STOPPED

            return True

        except OSError:

            return False

    # ------------------------------------------------------------------
    # CONTINUE
    # ------------------------------------------------------------------

    def continue_job(
        self,
        job_id: int,
    ) -> bool:

        job = self.get(job_id)

        if job is None:
            return False

        if os.name == "nt":

            return False

        try:

            os.kill(
                job.pid,
                signal.SIGCONT,
            )

            with job.lock:
                job.state = JobState.RUNNING

            return True

        except OSError:

            return False

    # ------------------------------------------------------------------
    # REMOVE
    # ------------------------------------------------------------------

    def remove(
        self,
        job_id: int,
    ) -> bool:

        with self._lock:

            if job_id not in self._jobs:
                return False

            job = self._jobs[job_id]

            if job.running:
                return False

            del self._jobs[job_id]

            return True

    # ------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------

    def cleanup_finished(
        self,
    ) -> int:

        removed = 0

        with self._lock:

            job_ids = list(
                self._jobs.keys()
            )

        for job_id in job_ids:

            job = self.get(job_id)

            if job is None:
                continue

            self.update(job)

            if not job.running:

                if self.remove(job_id):

                    removed += 1

        return removed

    # ------------------------------------------------------------------
    # TERMINATE ALL
    # ------------------------------------------------------------------

    def terminate_all(self) -> int:

        jobs = self.list_jobs(
            include_finished=False
        )

        count = 0

        for job in jobs:

            if self.terminate(
                job.job_id
            ):
                count += 1

        return count


# ---------------------------------------------------------------------------
# GLOBAL MANAGER
# ---------------------------------------------------------------------------

job_manager = JobManager()


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def register_job(
    process: subprocess.Popen,
    command: str,
    *,
    background: bool = False,
    cwd: Optional[str] = None,
) -> Job:

    job = job_manager.register(
        process,
        command,
        background=background,
        cwd=cwd,
    )

    job_manager.monitor(job)

    return job


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
        timeout,
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
    "register_job",
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
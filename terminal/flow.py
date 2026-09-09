"""
Convexity Terminal - Flow Engine
Version: 1.0.0

A Flow is a structured, reusable sequence of actions that can be:

    - created by Maple
    - created manually
    - saved
    - loaded
    - inspected
    - paused
    - resumed
    - cancelled
    - reused
    - executed through Convexity's executor

Important:
    This module does not bypass Convexity execution or Maple approval.

Recommended execution path:

    Maple
      ↓
    Flow
      ↓
    Approval / analysis
      ↓
    Executor
      ↓
    Operating system
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
import json
import time
import uuid


VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Flow state
# ---------------------------------------------------------------------------

class FlowState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Flow step
# ---------------------------------------------------------------------------

@dataclass
class FlowStep:
    """
    One operation inside a Convexity flow.

    command:
        Command intended for Convexity's executor.

    description:
        Human-readable explanation of what the step does.

    approval_required:
        Optional explicit Maple requirement.

    metadata:
        Additional information supplied by Maple or another component.
    """

    id: str
    command: str

    description: str = ""

    approval_required: bool = False

    state: StepState = StepState.PENDING

    output: str = ""
    error: str = ""

    exit_code: Optional[int] = None

    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------

@dataclass
class Flow:
    """
    Complete reusable workflow.
    """

    id: str
    name: str

    description: str = ""

    steps: list[FlowStep] = field(default_factory=list)

    state: FlowState = FlowState.DRAFT

    current_step: int = 0

    created_at: float = field(
        default_factory=time.time
    )

    updated_at: float = field(
        default_factory=time.time
    )

    created_by: str = "user"

    metadata: dict[str, Any] = field(default_factory=dict)

    # -----------------------------------------------------------------------
    # Add step
    # -----------------------------------------------------------------------

    def add_step(
        self,
        command: str,
        *,
        description: str = "",
        approval_required: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> FlowStep:

        if not isinstance(command, str):
            raise TypeError("command must be a string")

        if not command.strip():
            raise ValueError("command cannot be empty")

        step = FlowStep(
            id=str(uuid.uuid4()),
            command=command,
            description=description,
            approval_required=approval_required,
            metadata=metadata or {},
        )

        self.steps.append(step)

        self.state = FlowState.READY
        self.updated_at = time.time()

        return step

    # -----------------------------------------------------------------------
    # Remove step
    # -----------------------------------------------------------------------

    def remove_step(
        self,
        index: int,
    ) -> FlowStep:

        step = self.steps.pop(index)

        self.current_step = min(
            self.current_step,
            len(self.steps),
        )

        self.updated_at = time.time()

        return step

    # -----------------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------------

    def reset(self) -> None:

        for step in self.steps:

            step.state = StepState.PENDING
            step.output = ""
            step.error = ""
            step.exit_code = None
            step.started_at = None
            step.completed_at = None

        self.current_step = 0

        self.state = (
            FlowState.READY
            if self.steps
            else FlowState.DRAFT
        )

        self.updated_at = time.time()

    # -----------------------------------------------------------------------
    # Current step
    # -----------------------------------------------------------------------

    def get_current_step(self) -> Optional[FlowStep]:

        if not self.steps:
            return None

        if self.current_step >= len(self.steps):
            return None

        return self.steps[self.current_step]

    # -----------------------------------------------------------------------
    # Completion
    # -----------------------------------------------------------------------

    @property
    def completed(self) -> bool:

        return (
            bool(self.steps)
            and all(
                step.state in (
                    StepState.COMPLETED,
                    StepState.SKIPPED,
                )
                for step in self.steps
            )
        )

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:

        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Flow":

        steps = []

        for raw_step in data.get("steps", []):

            raw_step = dict(raw_step)

            raw_step["state"] = StepState(
                raw_step.get(
                    "state",
                    StepState.PENDING.value,
                )
            )

            steps.append(
                FlowStep(**raw_step)
            )

        raw = dict(data)

        raw["state"] = FlowState(
            raw.get(
                "state",
                FlowState.DRAFT.value,
            )
        )

        raw["steps"] = steps

        return cls(**raw)


# ---------------------------------------------------------------------------
# Flow execution result
# ---------------------------------------------------------------------------

@dataclass
class FlowResult:

    flow_id: str

    state: FlowState

    successful: bool

    completed_steps: int

    total_steps: int

    failed_step: Optional[int] = None

    message: str = ""


# ---------------------------------------------------------------------------
# Flow storage
# ---------------------------------------------------------------------------

class FlowStore:
    """
    Persistent local flow storage.

    Default location:

        ~/.convexity/flows/

    Each flow is stored as a JSON file.

    This makes flows reusable between terminal sessions.
    """

    def __init__(
        self,
        directory: Optional[str | Path] = None,
    ) -> None:

        self.directory = Path(
            directory
            if directory is not None
            else Path.home() / ".convexity" / "flows"
        )

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # -----------------------------------------------------------------------
    # Path
    # -----------------------------------------------------------------------

    def path_for(
        self,
        flow_id: str,
    ) -> Path:

        safe_id = "".join(
            character
            for character in flow_id
            if character.isalnum()
            or character
            in ("-", "_")
        )

        if not safe_id:
            raise ValueError("invalid flow id")

        return self.directory / f"{safe_id}.json"

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def save(
        self,
        flow: Flow,
    ) -> Path:

        flow.updated_at = time.time()

        path = self.path_for(flow.id)

        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(
                flow.to_dict(),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary.replace(path)

        return path

    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------

    def load(
        self,
        flow_id: str,
    ) -> Flow:

        path = self.path_for(flow_id)

        if not path.exists():
            raise FileNotFoundError(
                f"flow not found: {flow_id}"
            )

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return Flow.from_dict(data)

    # -----------------------------------------------------------------------
    # Delete
    # -----------------------------------------------------------------------

    def delete(
        self,
        flow_id: str,
    ) -> None:

        path = self.path_for(flow_id)

        if path.exists():
            path.unlink()

    # -----------------------------------------------------------------------
    # List
    # -----------------------------------------------------------------------

    def list_flows(self) -> list[Flow]:

        flows = []

        for path in self.directory.glob("*.json"):

            try:

                data = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                flows.append(
                    Flow.from_dict(data)
                )

            except (
                OSError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue

        flows.sort(
            key=lambda flow: flow.updated_at,
            reverse=True,
        )

        return flows


# ---------------------------------------------------------------------------
# Flow engine
# ---------------------------------------------------------------------------

class FlowEngine:
    """
    Executes flows through an injected executor.

    The executor is intentionally not hard-coded.

    This prevents the Flow Engine from becoming another independent
    execution system.

    Example executor contract:

        executor(command) -> result

    The returned object may provide:

        returncode
        stdout
        stderr

    """

    def __init__(
        self,
        executor: Optional[Callable[[str], Any]] = None,
        store: Optional[FlowStore] = None,
        approval_controller: Optional[Any] = None,
    ) -> None:

        self.executor = executor
        self.store = store or FlowStore()
        self.approval_controller = approval_controller

        self._cancel_requested = False
        self._pause_requested = False

    # -----------------------------------------------------------------------
    # Attach executor
    # -----------------------------------------------------------------------

    def set_executor(
        self,
        executor: Callable[[str], Any],
    ) -> None:

        self.executor = executor

    # -----------------------------------------------------------------------
    # Attach approval system
    # -----------------------------------------------------------------------

    def set_approval_controller(
        self,
        controller: Any,
    ) -> None:

        self.approval_controller = controller

    # -----------------------------------------------------------------------
    # Pause
    # -----------------------------------------------------------------------

    def pause(self) -> None:

        self._pause_requested = True

    # -----------------------------------------------------------------------
    # Resume
    # -----------------------------------------------------------------------

    def resume(self) -> None:

        self._pause_requested = False

    # -----------------------------------------------------------------------
    # Cancel
    # -----------------------------------------------------------------------

    def cancel(self) -> None:

        self._cancel_requested = True

    # -----------------------------------------------------------------------
    # Execute
    # -----------------------------------------------------------------------

    def execute(
        self,
        flow: Flow,
        *,
        save_progress: bool = True,
    ) -> FlowResult:

        if self.executor is None:

            raise RuntimeError(
                "FlowEngine requires an executor"
            )

        if not flow.steps:

            flow.state = FlowState.COMPLETED

            return FlowResult(
                flow_id=flow.id,
                state=flow.state,
                successful=True,
                completed_steps=0,
                total_steps=0,
                message="Flow contains no steps.",
            )

        self._cancel_requested = False

        flow.state = FlowState.RUNNING

        if save_progress:
            self.store.save(flow)

        for index in range(
            flow.current_step,
            len(flow.steps),
        ):

            step = flow.steps[index]

            # ---------------------------------------------------------------
            # Pause
            # ---------------------------------------------------------------

            if self._pause_requested:

                flow.state = FlowState.PAUSED
                flow.current_step = index

                if save_progress:
                    self.store.save(flow)

                return FlowResult(
                    flow_id=flow.id,
                    state=flow.state,
                    successful=False,
                    completed_steps=index,
                    total_steps=len(flow.steps),
                    message="Flow paused.",
                )

            # ---------------------------------------------------------------
            # Cancel
            # ---------------------------------------------------------------

            if self._cancel_requested:

                step.state = StepState.CANCELLED

                flow.state = FlowState.CANCELLED
                flow.current_step = index

                if save_progress:
                    self.store.save(flow)

                return FlowResult(
                    flow_id=flow.id,
                    state=flow.state,
                    successful=False,
                    completed_steps=index,
                    total_steps=len(flow.steps),
                    failed_step=index,
                    message="Flow cancelled.",
                )

            # ---------------------------------------------------------------
            # Maple approval
            # ---------------------------------------------------------------

            if self.approval_controller is not None:

                try:

                    request = (
                        self.approval_controller.inspect(
                            step.command,
                            action=step.command,
                            description=step.description,
                        )
                    )

                    if request.requires_confirmation:

                        approved = (
                            self.approval_controller.confirm(
                                request
                            )
                        )

                        if not approved:

                            step.state = StepState.CANCELLED

                            flow.state = FlowState.CANCELLED
                            flow.current_step = index

                            if save_progress:
                                self.store.save(flow)

                            return FlowResult(
                                flow_id=flow.id,
                                state=flow.state,
                                successful=False,
                                completed_steps=index,
                                total_steps=len(flow.steps),
                                failed_step=index,
                                message=(
                                    "Maple/user approval was denied."
                                ),
                            )

                except AttributeError:
                    raise RuntimeError(
                        "Invalid approval controller."
                    )

            # ---------------------------------------------------------------
            # Execute
            # ---------------------------------------------------------------

            step.state = StepState.RUNNING
            step.started_at = time.time()

            flow.current_step = index

            if save_progress:
                self.store.save(flow)

            try:

                result = self.executor(
                    step.command
                )

                return_code = getattr(
                    result,
                    "returncode",
                    getattr(
                        result,
                        "exit_code",
                        0,
                    ),
                )

                stdout = getattr(
                    result,
                    "stdout",
                    "",
                )

                stderr = getattr(
                    result,
                    "stderr",
                    "",
                )

                if stdout is None:
                    stdout = ""

                if stderr is None:
                    stderr = ""

                step.output = str(stdout)
                step.error = str(stderr)

                step.exit_code = return_code

                if return_code not in (
                    None,
                    0,
                ):

                    step.state = StepState.FAILED
                    step.completed_at = time.time()

                    flow.state = FlowState.FAILED

                    if save_progress:
                        self.store.save(flow)

                    return FlowResult(
                        flow_id=flow.id,
                        state=flow.state,
                        successful=False,
                        completed_steps=index,
                        total_steps=len(flow.steps),
                        failed_step=index,
                        message=(
                            f"Step {index + 1} failed."
                        ),
                    )

                step.state = StepState.COMPLETED
                step.completed_at = time.time()

            except Exception as exc:

                step.state = StepState.FAILED
                step.error = str(exc)
                step.completed_at = time.time()

                flow.state = FlowState.FAILED

                if save_progress:
                    self.store.save(flow)

                return FlowResult(
                    flow_id=flow.id,
                    state=flow.state,
                    successful=False,
                    completed_steps=index,
                  
"""
Convexity Terminal - Maple Approval Layer
Version: 1.0.0

Purpose
-------
Provides Maple-aware danger detection and confirmation handling.

Important design principle
--------------------------
Convexity itself does NOT block normal user execution.

This module is primarily used when Maple is loaded and is preparing
to execute a task or flow.

Manual terminal usage:
    User -> Convexity -> OS

Maple usage:
    User -> Maple -> Analyze -> Plan -> Approval -> Convexity -> OS

The approval layer detects potentially destructive actions and asks
for confirmation before Maple executes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional
import re
import shlex


VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Approval levels
# ---------------------------------------------------------------------------

class ApprovalLevel(str, Enum):
    """
    Risk level assigned to an operation.

    SAFE:
        Normal operation. Maple can normally continue.

    NOTICE:
        Something worth explaining to the user, but not normally
        dangerous.

    CONFIRM:
        Potentially destructive or consequential. Maple should ask
        the user before continuing.

    CRITICAL:
        Extremely dangerous operation. Maple should require explicit
        confirmation and provide a clear explanation.
    """

    SAFE = "safe"
    NOTICE = "notice"
    CONFIRM = "confirm"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Approval decision
# ---------------------------------------------------------------------------

class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"
    NOT_REQUIRED = "not_required"


# ---------------------------------------------------------------------------
# Analysis result
# ---------------------------------------------------------------------------

@dataclass
class DangerFinding:
    """
    Describes one potentially dangerous aspect of an operation.
    """

    category: str
    level: ApprovalLevel
    reason: str
    matched_text: Optional[str] = None


@dataclass
class ApprovalRequest:
    """
    Represents a request Maple can present to the user.
    """

    action: str
    command: Optional[str] = None
    description: str = ""
    findings: list[DangerFinding] = field(default_factory=list)

    level: ApprovalLevel = ApprovalLevel.SAFE

    decision: ApprovalDecision = ApprovalDecision.PENDING

    approved_by_user: bool = False

    metadata: dict = field(default_factory=dict)

    @property
    def requires_confirmation(self) -> bool:
        return self.level in (
            ApprovalLevel.CONFIRM,
            ApprovalLevel.CRITICAL,
        )


# ---------------------------------------------------------------------------
# Dangerous operation definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DangerRule:
    name: str
    pattern: str
    level: ApprovalLevel
    category: str
    reason: str


DEFAULT_RULES: tuple[DangerRule, ...] = (

    # -----------------------------------------------------------------------
    # File deletion
    # -----------------------------------------------------------------------

    DangerRule(
        name="delete_command",
        pattern=r"\b(rm|rmdir|del|erase)\b",
        level=ApprovalLevel.CONFIRM,
        category="file_deletion",
        reason="This operation may permanently delete files or directories.",
    ),

    DangerRule(
        name="recursive_delete",
        pattern=r"\b(rm)\s+(-[a-zA-Z]*r|--recursive)",
        level=ApprovalLevel.CRITICAL,
        category="recursive_deletion",
        reason="Recursive deletion can remove large parts of the filesystem.",
    ),

    DangerRule(
        name="force_delete",
        pattern=r"\b(rm)\s+(-[a-zA-Z]*f|--force)",
        level=ApprovalLevel.CONFIRM,
        category="forced_deletion",
        reason="Forced deletion can remove files without normal safeguards.",
    ),

    # -----------------------------------------------------------------------
    # Disk operations
    # -----------------------------------------------------------------------

    DangerRule(
        name="format",
        pattern=r"\b(format|mkfs|diskpart)\b",
        level=ApprovalLevel.CRITICAL,
        category="disk_formatting",
        reason="Formatting can permanently destroy data on a storage device.",
    ),

    DangerRule(
        name="partition",
        pattern=r"\b(fdisk|gdisk|parted|diskpart)\b",
        level=ApprovalLevel.CRITICAL,
        category="partitioning",
        reason="Partition changes can make existing data inaccessible.",
    ),

    # -----------------------------------------------------------------------
    # System shutdown/reboot
    # -----------------------------------------------------------------------

    DangerRule(
        name="shutdown",
        pattern=r"\b(shutdown|poweroff|halt)\b",
        level=ApprovalLevel.CONFIRM,
        category="system_shutdown",
        reason="This will shut down the operating system.",
    ),

    DangerRule(
        name="reboot",
        pattern=r"\b(reboot|restart)\b",
        level=ApprovalLevel.CONFIRM,
        category="system_reboot",
        reason="This will restart the operating system.",
    ),

    # -----------------------------------------------------------------------
    # Privilege escalation
    # -----------------------------------------------------------------------

    DangerRule(
        name="sudo",
        pattern=r"\bsudo\b",
        level=ApprovalLevel.CONFIRM,
        category="privilege_escalation",
        reason="The command requests elevated system privileges.",
    ),

    DangerRule(
        name="runas",
        pattern=r"\brunas\b",
        level=ApprovalLevel.CONFIRM,
        category="privilege_escalation",
        reason="The command requests elevated Windows privileges.",
    ),

    # -----------------------------------------------------------------------
    # Permission changes
    # -----------------------------------------------------------------------

    DangerRule(
        name="chmod",
        pattern=r"\bchmod\b",
        level=ApprovalLevel.CONFIRM,
        category="permission_change",
        reason="This changes filesystem permissions.",
    ),

    DangerRule(
        name="chown",
        pattern=r"\bchown\b",
        level=ApprovalLevel.CONFIRM,
        category="ownership_change",
        reason="This changes filesystem ownership.",
    ),

    # -----------------------------------------------------------------------
    # Process termination
    # -----------------------------------------------------------------------

    DangerRule(
        name="kill_process",
        pattern=r"\b(kill|pkill|killall|taskkill)\b",
        level=ApprovalLevel.CONFIRM,
        category="process_control",
        reason="This may terminate a running process.",
    ),

    # -----------------------------------------------------------------------
    # Mounting
    # -----------------------------------------------------------------------

    DangerRule(
        name="mount",
        pattern=r"\b(mount|umount)\b",
        level=ApprovalLevel.CONFIRM,
        category="filesystem_mount",
        reason="This changes mounted filesystem state.",
    ),

    # -----------------------------------------------------------------------
    # Network/system configuration
    # -----------------------------------------------------------------------

    DangerRule(
        name="network_configuration",
        pattern=r"\b(ipconfig|ifconfig|netsh|iptables|nft|route)\b",
        level=ApprovalLevel.CONFIRM,
        category="network_configuration",
        reason="This may modify network configuration.",
    ),

    # -----------------------------------------------------------------------
    # Package removal
    # -----------------------------------------------------------------------

    DangerRule(
        name="package_remove",
        pattern=r"\b(apt|apt-get|apk|pacman|winget|choco)\b.*\b(remove|uninstall|purge)\b",
        level=ApprovalLevel.CONFIRM,
        category="package_removal",
        reason="This will remove software from the system.",
    ),

    # -----------------------------------------------------------------------
    # Git destructive operations
    # -----------------------------------------------------------------------

    DangerRule(
        name="git_reset_hard",
        pattern=r"\bgit\s+reset\s+.*--hard\b",
        level=ApprovalLevel.CONFIRM,
        category="git_destructive",
        reason="This can discard uncommitted changes.",
    ),

    DangerRule(
        name="git_clean",
        pattern=r"\bgit\s+clean\b.*-[a-zA-Z]*f",
        level=ApprovalLevel.CONFIRM,
        category="git_destructive",
        reason="This can permanently remove untracked files.",
    ),

    # -----------------------------------------------------------------------
    # Shell privilege / execution tricks
    # -----------------------------------------------------------------------

    DangerRule(
        name="shell_elevation",
        pattern=r"\b(doas|su)\b",
        level=ApprovalLevel.CONFIRM,
        category="privilege_escalation",
        reason="This may switch to another user or elevated account.",
    ),

    # -----------------------------------------------------------------------
    # Broad filesystem writes
    # -----------------------------------------------------------------------

    DangerRule(
        name="system_directory_write",
        pattern=(
            r"(\/etc\/|\/boot\/|\/sys\/|\/proc\/|\/dev\/)"
        ),
        level=ApprovalLevel.CONFIRM,
        category="system_filesystem",
        reason="The operation targets a sensitive operating-system path.",
    ),

    DangerRule(
        name="windows_system_directory",
        pattern=r"(?i)(C:\\Windows\\|C:\\Program Files\\|C:\\System32\\)",
        level=ApprovalLevel.CONFIRM,
        category="system_filesystem",
        reason="The operation targets a sensitive Windows system path.",
    ),
)


# ---------------------------------------------------------------------------
# Approval engine
# ---------------------------------------------------------------------------

class ApprovalEngine:
    """
    Maple's operation-risk analyzer.

    This class does not execute commands.

    It only answers:

        "Should Maple ask the user before executing this?"
    """

    def __init__(
        self,
        rules: Optional[Iterable[DangerRule]] = None,
    ) -> None:

        self.rules = list(
            rules if rules is not None else DEFAULT_RULES
        )

    # -----------------------------------------------------------------------
    # Analyze command
    # -----------------------------------------------------------------------

    def analyze_command(
        self,
        command: str,
        *,
        action: str = "execute_command",
        description: str = "",
    ) -> ApprovalRequest:

        if not isinstance(command, str):
            raise TypeError("command must be a string")

        findings: list[DangerFinding] = []

        for rule in self.rules:

            try:
                match = re.search(
                    rule.pattern,
                    command,
                    flags=re.IGNORECASE,
                )
            except re.error:
                continue

            if not match:
                continue

            findings.append(
                DangerFinding(
                    category=rule.category,
                    level=rule.level,
                    reason=rule.reason,
                    matched_text=match.group(0),
                )
            )

        level = self._highest_level(findings)

        return ApprovalRequest(
            action=action,
            command=command,
            description=description,
            findings=findings,
            level=level,
        )

    # -----------------------------------------------------------------------
    # Analyze structured operation
    # -----------------------------------------------------------------------

    def analyze_action(
        self,
        action: str,
        *,
        target: Optional[str] = None,
        description: str = "",
    ) -> ApprovalRequest:

        combined = action

        if target:
            combined += " " + target

        return self.analyze_command(
            combined,
            action=action,
            description=description,
        )

    # -----------------------------------------------------------------------
    # Determine highest danger level
    # -----------------------------------------------------------------------

    @staticmethod
    def _highest_level(
        findings: list[DangerFinding],
    ) -> ApprovalLevel:

        if not findings:
            return ApprovalLevel.SAFE

        priority = {
            ApprovalLevel.SAFE: 0,
            ApprovalLevel.NOTICE: 1,
            ApprovalLevel.CONFIRM: 2,
            ApprovalLevel.CRITICAL: 3,
        }

        return max(
            (finding.level for finding in findings),
            key=lambda value: priority[value],
        )

    # -----------------------------------------------------------------------
    # Is confirmation required?
    # -----------------------------------------------------------------------

    def requires_confirmation(
        self,
        request: ApprovalRequest,
    ) -> bool:

        return request.requires_confirmation

    # -----------------------------------------------------------------------
    # Generate user-facing explanation
    # -----------------------------------------------------------------------

    def explain(
        self,
        request: ApprovalRequest,
    ) -> str:

        if not request.findings:
            return "No potentially dangerous operation was detected."

        lines = []

        if request.level == ApprovalLevel.CRITICAL:
            lines.append(
                "Maple detected a potentially critical operation."
            )

        elif request.level == ApprovalLevel.CONFIRM:
            lines.append(
                "Maple detected an operation that may cause significant changes."
            )

        elif request.level == ApprovalLevel.NOTICE:
            lines.append(
                "Maple detected an operation worth reviewing."
            )

        for finding in request.findings:

            lines.append(
                f"- {finding.reason}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Confirmation provider
# ---------------------------------------------------------------------------

class ConfirmationProvider:
    """
    Interface used by Maple to obtain user approval.

    The default implementation works in a terminal.

    A GUI application can replace this with a graphical confirmation
    dialog without changing the approval engine.
    """

    def confirm(
        self,
        request: ApprovalRequest,
    ) -> bool:

        raise NotImplementedError


class TerminalConfirmationProvider(ConfirmationProvider):
    """
    Simple terminal-based confirmation provider.
    """

    def confirm(
        self,
        request: ApprovalRequest,
    ) -> bool:

        print()
        print("=" * 64)
        print("MAPLE SAFETY CONFIRMATION")
        print("=" * 64)

        if request.description:
            print()
            print(request.description)

        if request.command:
            print()
            print("Planned command:")
            print(request.command)

        print()
        print("Reason:")

        for finding in request.findings:
            print(f"  - {finding.reason}")

        print()

        if request.level == ApprovalLevel.CRITICAL:
            print(
                "WARNING: This operation may cause irreversible damage."
            )

        answer = input(
            "\nMaple: Continue? [y/N]: "
        ).strip().lower()

        approved = answer in {
            "y",
            "yes",
        }

        request.approved_by_user = approved

        request.decision = (
            ApprovalDecision.APPROVED
            if approved
            else ApprovalDecision.DENIED
        )

        return approved


# ---------------------------------------------------------------------------
# Maple approval controller
# ---------------------------------------------------------------------------

class MapleApprovalController:
    """
    High-level interface Maple can use before executing a planned action.

    Typical flow:

        request = controller.inspect(command)

        if request.requires_confirmation:
            approved = controller.confirm(request)

        if approved:
            executor.execute(...)
    """

    def __init__(
        self,
        engine: Optional[ApprovalEngine] = None,
        confirmation_provider: Optional[ConfirmationProvider] = None,
    ) -> None:

        self.engine = engine or ApprovalEngine()

        self.confirmation_provider = (
            confirmation_provider
            or TerminalConfirmationProvider()
        )

    # -----------------------------------------------------------------------
    # Inspect
    # -----------------------------------------------------------------------

    def inspect(
        self,
        command: str,
        *,
        action: str = "execute_command",
        description: str = "",
    ) -> ApprovalRequest:

        return self.engine.analyze_command(
            command,
            action=action,
            description=description,
        )

    # -----------------------------------------------------------------------
    # Approve
    # -----------------------------------------------------------------------

    def confirm(
        self,
        request: ApprovalRequest,
    ) -> bool:

        if not request.requires_confirmation:

            request.decision = (
                ApprovalDecision.NOT_REQUIRED
            )

            return True

        return self.confirmation_provider.confirm(
            request
        )

    # -----------------------------------------------------------------------
    # Complete Maple check
    # -----------------------------------------------------------------------

    def authorize(
        self,
        command: str,
        *,
        action: str = "execute_command",
        description: str = "",
    ) -> ApprovalRequest:

        request = self.inspect(
            command,
            action=action,
            description=description,
        )

        self.confirm(request)

        return request


# ---------------------------------------------------------------------------
# Flow-level approval
# ---------------------------------------------------------------------------

@dataclass
class FlowApprovalResult:
    """
    Result of analyzing an entire Maple flow.
    """

    approved: bool
    requests: list[ApprovalRequest]

    @property
    def dangerous_steps(self) -> list[ApprovalRequest]:
        return [
            request
            for request in self.requests
            if request.requires_confirmation
        ]


class FlowApprovalController:
    """
    Analyzes a complete Maple flow before or during execution.

    This allows Maple to explain a planned workflow before beginning it.

    Example:

        Download model
        Create HTML interface
        Install llama.cpp
        Start server

    If a later step would delete an existing directory, Maple can detect
    that step and request approval.
    """

    def __init__(
        self,
        approval_co
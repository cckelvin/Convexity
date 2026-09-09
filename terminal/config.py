"""
Convexity Terminal Configuration
Version: 0.2.0

Central configuration for:
- terminal behavior
- filesystem sandbox
- command execution
- security
- permissions
- output limits
- environment handling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet


@dataclass
class TerminalConfig:
    """Central configuration for the Convexity Terminal."""

    # ---------------------------------------------------------
    # APPLICATION
    # ---------------------------------------------------------

    APP_NAME: str = "Convexity"
    VERSION: str = "0.2.0"

    # ---------------------------------------------------------
    # EXECUTION
    # ---------------------------------------------------------

    DEFAULT_TIMEOUT: int = 30

    MAX_OUTPUT_LENGTH: int = 100_000

    MAX_FILE_READ_SIZE: int = 10_000_000

    # ---------------------------------------------------------
    # SECURITY
    # ---------------------------------------------------------

    SANDBOX_ENABLED: bool = True

    REQUIRE_CONFIRMATION_FOR_DANGEROUS_ACTIONS: bool = True

    # Shell execution is supported by the architecture,
    # but Maple must never automatically receive unrestricted
    # shell access.
    ALLOW_SHELL_COMMANDS: bool = True

    # ---------------------------------------------------------
    # SANDBOX
    # ---------------------------------------------------------

    # None means the Convexity working directory.
    SANDBOX_ROOT: str | None = None

    # ---------------------------------------------------------
    # COMMAND POLICY
    # ---------------------------------------------------------

    # Commands allowed to execute as external processes.
    #
    # This is intentionally configurable because different
    # operating systems have different available programs.
    ALLOWED_EXTERNAL_COMMANDS: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {
                # Python
                "python",
                "python3",

                # JavaScript
                "node",
                "npm",
                "npx",

                # Version control
                "git",

                # Common development tools
                "gcc",
                "g++",
                "javac",
                "java",

                # Archive tools
                "tar",
                "zip",
                "unzip",

                # Information utilities
                "whoami",
                "hostname",
                "where",
                "which",

                # Common text utilities
                "grep",
                "find",
                "head",
                "tail",
                "sort",
                "uniq",
            }
        )
    )

    # ---------------------------------------------------------
    # COMMANDS REQUIRING EXTRA PERMISSION
    # ---------------------------------------------------------

    DANGEROUS_COMMANDS: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {
                "rm",
                "rmdir",
                "del",
                "erase",
                "format",
                "mkfs",
                "fdisk",
                "diskpart",
                "shutdown",
                "reboot",
                "poweroff",
                "kill",
                "pkill",
                "taskkill",
                "sudo",
                "runas",
                "chmod",
                "chown",
                "mount",
                "umount",
            }
        )
    )

    # ---------------------------------------------------------
    # DANGEROUS ARGUMENT/PATTERN CHECKS
    # ---------------------------------------------------------

    DANGEROUS_PATTERNS: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {
                "rm -rf /",
                "rm -rf /*",
                "rm -r /",
                "mkfs",
                "fdisk",
                "diskpart",
                "format c:",
                "format c\\",
                "dd if=",
                "> /dev/sda",
                "> /dev/nvme",
                ":(){",
                "fork bomb",
                "shutdown /s",
                "shutdown -h",
                "reboot",
                "poweroff",
            }
        )
    )

    # ---------------------------------------------------------
    # SHELL OPERATORS
    # ---------------------------------------------------------

    # These are recognized so the security layer can decide
    # whether piping/redirection/chaining is permitted.
    SHELL_OPERATORS: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {
                "|",
                "||",
                "&&",
                ";",
                ">",
                ">>",
                "<",
                "<<",
                "&",
            }
        )
    )

    # ---------------------------------------------------------
    # ENVIRONMENT
    # ---------------------------------------------------------

    # Environment variables that may safely be exposed to
    # child processes.
    #
    # Secrets should NOT automatically be forwarded.
    ALLOWED_ENVIRONMENT_VARIABLES: FrozenSet[str] = field(
        default_factory=lambda: frozenset(
            {
                "PATH",
                "HOME",
                "USER",
                "USERNAME",
                "TEMP",
                "TMP",
                "TMPDIR",
                "LANG",
                "LC_ALL",
                "LC_CTYPE",
                "TERM",
                "SHELL",
                "COMSPEC",
                "SYSTEMROOT",
                "SYSTEMDRIVE",
                "PATHEXT",
                "APPDATA",
                "LOCALAPPDATA",
                "PROGRAMFILES",
                "PROGRAMFILES(X86)",
            }
        )
    )

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------

    HISTORY_FILENAME: str = ".convexity_history"

    MAX_HISTORY_ENTRIES: int = 1000

    # ---------------------------------------------------------
    # FILESYSTEM
    # ---------------------------------------------------------

    MAX_PATH_LENGTH: int = 4096

    # ---------------------------------------------------------
    # MAPLE
    # ---------------------------------------------------------

    # Maple is not implemented yet, but these settings allow
    # the terminal to have a stable future interface.
    MAPLE_ENABLED: bool = False

    MAPLE_REQUIRE_PERMISSION: bool = True

    # ---------------------------------------------------------
    # CONFIGURATION METHODS
    # ---------------------------------------------------------

    def get_sandbox_root(self) -> Path:
        """
        Return the absolute sandbox directory.
        """

        if self.SANDBOX_ROOT:
            root = Path(self.SANDBOX_ROOT).expanduser()
        else:
            root = Path.cwd()

        return root.resolve()

    def get_history_path(self) -> Path:
        """
        Return the Convexity command history path.
        """

        return Path.home() / self.HISTORY_FILENAME

    def is_command_allowed(self, command: str) -> bool:
        """
        Check whether an executable is present in the
        external-command allowlist.
        """

        return command.lower() in self.ALLOWED_EXTERNAL_COMMANDS

    def is_dangerous_command(self, command: str) -> bool:
        """
        Check whether a command name is classified as dangerous.
        """

        return command.lower() in self.DANGEROUS_COMMANDS

    def contains_dangerous_pattern(self, command: str) -> bool:
        """
        Check the complete command for known dangerous patterns.
        """

        lowered = command.lower()

        return any(
            pattern.lower() in lowered
            for pattern in self.DANGEROUS_PATTERNS
        )

    def should_expose_environment_variable(self, name: str) -> bool:
        """
        Determine whether an environment variable may be passed
        to an external process.
        """

        return name.upper() in {
            variable.upper()
            for variable in self.ALLOWED_ENVIRONMENT_VARIABLES
        }


# Global Convexity configuration instance.
config = TerminalConfig()
"""
Convexity Terminal Configuration.

Defines global settings, security policies, and application metadata.
"""

from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class TerminalConfig:
    """Central configuration for the Convexity Terminal."""
    
    # Application Metadata
    APP_NAME: str = "Convexity"
    VERSION: str = "0.1.0"
    
    # Execution Constraints
    DEFAULT_TIMEOUT: int = 30  # seconds
    MAX_OUTPUT_LENGTH: int = 10000  # characters
    
    # Security Policies
    ALLOW_SHELL_COMMANDS: bool = False  # If False, only allowlisted commands run via subprocess
    REQUIRE_CONFIRMATION_FOR_DANGEROUS_ACTIONS: bool = True
    SANDBOX_ENABLED: bool = True
    
    # Filesystem Constraints
    # If SANDBOX_ENABLED is True, operations are restricted to this root.
    # If None, defaults to the current working directory at startup.
    SANDBOX_ROOT: str = field(default_factory=lambda: ".")
    
    # Allowed External Commands (Allowlist)
    # These are commands that can be executed via subprocess if not handled internally.
    ALLOWED_EXTERNAL_COMMANDS: Set[str] = field(default_factory=lambda: {
        "python", "python3", "pip", "git", "node", "npm", "curl", "wget", "grep", "find"
    })
    
    # Dangerous Command Patterns (for additional heuristic checking)
    DANGEROUS_PATTERNS: List[str] = field(default_factory=lambda: [
        "rm -rf /", "dd if=", ":(){ :|:& };:", "> /dev/sda", "mkfs", "fdisk"
    ])

    def get_sandbox_root(self) -> str:
        """Returns the resolved absolute path of the sandbox root."""
        import os
        from pathlib import Path
        
        if self.SANDBOX_ROOT:
            return str(Path(self.SANDBOX_ROOT).resolve())
        return str(Path.cwd().resolve())

# Global instance for easy access within the package
config = TerminalConfig()

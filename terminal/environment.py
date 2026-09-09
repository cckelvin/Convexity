"""
Convexity Environment Engine
Version 0.4.0

Provides Convexity-native:
- environment variables
- shell variables
- variable expansion
- ${VAR} syntax
- $VAR syntax
- %VAR% compatibility
- aliases
- variable listing
- variable removal
- command substitution foundation

This module does not execute shell commands itself.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable


# ---------------------------------------------------------------------------
# VARIABLE PATTERNS
# ---------------------------------------------------------------------------

DOLLAR_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
)

SIMPLE_DOLLAR_PATTERN = re.compile(
    r"\$([A-Za-z_][A-Za-z0-9_]*)"
)

WINDOWS_PATTERN = re.compile(
    r"%([A-Za-z_][A-Za-z0-9_]*)%"
)


# ---------------------------------------------------------------------------
# RESULT TYPES
# ---------------------------------------------------------------------------

@dataclass
class VariableResult:
    success: bool
    value: str = ""
    error: str = ""


@dataclass
class Alias:
    name: str
    value: str


# ---------------------------------------------------------------------------
# ENVIRONMENT ENGINE
# ---------------------------------------------------------------------------

class ConvexityEnvironment:
    """
    Manages Convexity's shell environment.

    Shell variables are kept separate from the host process environment.

    This allows Convexity to have its own environment while still exposing
    selected operating-system variables when required.
    """

    def __init__(
        self,
        initial_environment: Optional[
            Dict[str, str]
        ] = None,
    ) -> None:

        self.variables: Dict[str, str] = {}

        self.aliases: Dict[str, str] = {}

        self.functions: Dict[str, str] = {}

        self._load_environment(
            initial_environment
        )

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def _load_environment(
        self,
        initial_environment: Optional[
            Dict[str, str]
        ],
    ) -> None:

        source = (
            initial_environment
            if initial_environment is not None
            else os.environ
        )

        for key, value in source.items():

            if isinstance(key, str):

                self.variables[key] = str(value)

    # ------------------------------------------------------------------
    # VARIABLE NAMES
    # ------------------------------------------------------------------

    @staticmethod
    def valid_name(name: str) -> bool:

        if not name:
            return False

        return bool(
            re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                name,
            )
        )

    # ------------------------------------------------------------------
    # SET
    # ------------------------------------------------------------------

    def set(
        self,
        name: str,
        value: str,
    ) -> VariableResult:

        if not self.valid_name(name):

            return VariableResult(
                success=False,
                error=(
                    f"Invalid variable name: {name}"
                ),
            )

        self.variables[name] = str(value)

        return VariableResult(
            success=True,
            value=str(value),
        )

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def get(
        self,
        name: str,
        default: str = "",
    ) -> str:

        return self.variables.get(
            name,
            default,
        )

    # ------------------------------------------------------------------
    # EXISTS
    # ------------------------------------------------------------------

    def exists(
        self,
        name: str,
    ) -> bool:

        return name in self.variables

    # ------------------------------------------------------------------
    # UNSET
    # ------------------------------------------------------------------

    def unset(
        self,
        name: str,
    ) -> VariableResult:

        if name in self.variables:

            del self.variables[name]

            return VariableResult(
                success=True
            )

        return VariableResult(
            success=False,
            error=(
                f"Variable '{name}' does not exist."
            ),
        )

    # ------------------------------------------------------------------
    # CLEAR
    # ------------------------------------------------------------------

    def clear(self) -> None:

        self.variables.clear()

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def list_variables(
        self,
    ) -> Dict[str, str]:

        return dict(
            sorted(
                self.variables.items(),
                key=lambda item: item[0].lower(),
            )
        )

    # ------------------------------------------------------------------
    # ALIASES
    # ------------------------------------------------------------------

    def set_alias(
        self,
        name: str,
        command: str,
    ) -> VariableResult:

        if not name:

            return VariableResult(
                success=False,
                error="Alias name cannot be empty.",
            )

        if any(
            char.isspace()
            for char in name
        ):

            return VariableResult(
                success=False,
                error="Alias name cannot contain spaces.",
            )

        self.aliases[name] = command

        return VariableResult(
            success=True,
            value=command,
        )

    def get_alias(
        self,
        name: str,
    ) -> Optional[str]:

        return self.aliases.get(name)

    def remove_alias(
        self,
        name: str,
    ) -> VariableResult:

        if name not in self.aliases:

            return VariableResult(
                success=False,
                error=(
                    f"Alias '{name}' does not exist."
                ),
            )

        del self.aliases[name]

        return VariableResult(
            success=True
        )

    def list_aliases(
        self,
    ) -> Dict[str, str]:

        return dict(
            sorted(
                self.aliases.items(),
                key=lambda item: item[0].lower(),
            )
        )

    # ------------------------------------------------------------------
    # FUNCTIONS
    # ------------------------------------------------------------------

    def set_function(
        self,
        name: str,
        body: str,
    ) -> VariableResult:

        if not self.valid_name(name):

            return VariableResult(
                success=False,
                error=(
                    f"Invalid function name: {name}"
                ),
            )

        self.functions[name] = body

        return VariableResult(
            success=True,
            value=body,
        )

    def get_function(
        self,
        name: str,
    ) -> Optional[str]:

        return self.functions.get(name)

    def remove_function(
        self,
        name: str,
    ) -> VariableResult:

        if name not in self.functions:

            return VariableResult(
                success=False,
                error=(
                    f"Function '{name}' does not exist."
                ),
            )

        del self.functions[name]

        return VariableResult(
            success=True
        )

    # ------------------------------------------------------------------
    # EXPANSION
    # ------------------------------------------------------------------

    def expand(
        self,
        text: str,
        *,
        include_windows_style: bool = True,
        keep_missing: bool = False,
    ) -> str:

        if not text:
            return text

        # ${VARIABLE}
        text = DOLLAR_PATTERN.sub(
            lambda match: self._replacement(
                match.group(1),
                keep_missing,
            ),
            text,
        )

        # $VARIABLE
        text = SIMPLE_DOLLAR_PATTERN.sub(
            lambda match: self._replacement(
                match.group(1),
                keep_missing,
            ),
            text,
        )

        # %VARIABLE%
        if include_windows_style:

            text = WINDOWS_PATTERN.sub(
                lambda match: self._replacement(
                    match.group(1),
                    keep_missing,
                ),
                text,
            )

        return text

    def _replacement(
        self,
        name: str,
        keep_missing: bool,
    ) -> str:

        if name in self.variables:

            return self.variables[name]

        if keep_missing:

            return f"${name}"

        return ""

    # ------------------------------------------------------------------
    # COMMAND ARGUMENT EXPANSION
    # ------------------------------------------------------------------

    def expand_arguments(
        self,
        arguments: list[str],
    ) -> list[str]:

        return [
            self.expand(argument)
            for argument in arguments
        ]

    # ------------------------------------------------------------------
    # ALIAS EXPANSION
    # ------------------------------------------------------------------

    def expand_alias(
        self,
        command: str,
    ) -> str:

        stripped = command.lstrip()

        if not stripped:
            return command

        parts = stripped.split(
            maxsplit=1
        )

        command_name = parts[0]

        alias = self.get_alias(
            command_name
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

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_environment(self) -> Dict[str, str]:

        return dict(self.variables)

    # ------------------------------------------------------------------
    # HOST ENVIRONMENT SYNC
    # ------------------------------------------------------------------

    def sync_to_process_environment(
        self,
    ) -> Dict[str, str]:

        environment = dict(
            os.environ
        )

        environment.update(
            self.variables
        )

        return environment

    # ------------------------------------------------------------------
    # IMPORT ONE HOST VARIABLE
    # ------------------------------------------------------------------

    def import_host_variable(
        self,
        name: str,
    ) -> VariableResult:

        if name not in os.environ:

            return VariableResult(
                success=False,
                error=(
                    f"Host variable '{name}' does not exist."
                ),
            )

        self.variables[name] = os.environ[name]

        return VariableResult(
            success=True,
            value=os.environ[name],
        )


# ---------------------------------------------------------------------------
# SPECIAL VARIABLES
# ---------------------------------------------------------------------------

@dataclass
class ShellState:

    last_exit_code: int = 0
    last_command: str = ""
    command_count: int = 0

    def update(
        self,
        command: str,
        exit_code: int,
    ) -> None:

        self.last_command = command
        self.last_exit_code = exit_code
        self.command_count += 1

    def variables(self) -> Dict[str, str]:

        return {
            "?": str(self.last_exit_code),
            "LAST_EXIT_CODE": str(
                self.last_exit_code
            ),
            "LAST_COMMAND": self.last_command,
            "COMMAND_COUNT": str(
                self.command_count
            ),
        }


# ---------------------------------------------------------------------------
# COMPLETE SHELL CONTEXT
# ---------------------------------------------------------------------------

class ShellContext:

    def __init__(
        self,
        environment: Optional[
            ConvexityEnvironment
        ] = None,
    ) -> None:

        self.environment = (
            environment
            if environment is not None
            else ConvexityEnvironment()
        )

        self.state = ShellState()

    def expand(
        self,
        text: str,
    ) -> str:

        expanded = self.environment.expand(
            text
        )

        special = self.state.variables()

        for name, value in special.items():

            expanded = expanded.replace(
                f"${name}",
                value,
            )

        return expanded

    def update_result(
        self,
        command: str,
        exit_code: int,
    ) -> None:

        self.state.update(
            command,
            exit_code,
        )


# ---------------------------------------------------------------------------
# GLOBAL CONTEXT
# ---------------------------------------------------------------------------

context = ShellContext()


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------------------------

def set_variable(
    name: str,
    value: str,
) -> VariableResult:

    return context.environment.set(
        name,
        value,
    )


def get_variable(
    name: str,
    default: str = "",
) -> str:

    return context.environment.get(
        name,
        default,
    )


def unset_variable(
    name: str,
) -> VariableResult:

    return context.environment.unset(
        name
    )


def expand_variables(
    text: str,
) -> str:

    return context.expand(
        text
    )


def set_alias(
    name: str,
    command: str,
) -> VariableResult:

    return context.environment.set_alias(
        name,
        command,
    )


def get_alias(
    name: str,
) -> Optional[str]:

    return context.environment.get_alias(
        name
    )


def remove_alias(
    name: str,
) -> VariableResult:

    return context.environment.remove_alias(
        name
    )


__all__ = [
    "VariableResult",
    "Alias",
    "ConvexityEnvironment",
    "ShellState",
    "ShellContext",
    "context",
    "set_variable",
    "get_variable",
    "unset_variable",
    "expand_variables",
    "set_alias",
    "get_alias",
    "remove_alias",
]
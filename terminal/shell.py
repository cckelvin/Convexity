"""
Convexity Native Shell Engine
Version 0.3.0

Convexity's own shell parser.

Supported:
    command
    command | command
    command > file
    command >> file
    command < file
    command && command
    command || command
    command ; command
    command &

Quoted arguments are supported.

This module does NOT use shell=True.
Every executable command is still routed through Convexity's
security and execution layers.
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from typing import List, Optional

from .config import config
from .executor import (
    ExecutionResult,
    execute_command,
    execute_pipeline,
    start_background,
)


# ---------------------------------------------------------------------------
# TOKEN TYPES
# ---------------------------------------------------------------------------

OPERATORS = (
    "&&",
    "||",
    ">>",
    "|",
    ">",
    "<",
    ";",
    "&",
)


@dataclass
class ShellCommand:
    """One parsed shell command."""

    command: str
    stdin: Optional[str] = None
    stdout: Optional[str] = None
    append_stdout: bool = False
    background: bool = False


@dataclass
class ShellExpression:
    """A complete parsed shell expression."""

    commands: List[ShellCommand]
    operators: List[str]


# ---------------------------------------------------------------------------
# LEXER
# ---------------------------------------------------------------------------

def tokenize_shell(command: str) -> List[str]:
    """
    Convert shell text into tokens while preserving operators.

    Example:

        echo "hello world" | grep hello > result.txt

    becomes approximately:

        echo
        hello world
        |
        grep
        hello
        >
        result.txt
    """

    if not command or not command.strip():
        return []

    tokens: List[str] = []
    current: List[str] = []

    quote: Optional[str] = None
    escaped = False

    index = 0

    while index < len(command):

        char = command[index]

        # --------------------------------------------------------------
        # ESCAPING
        # --------------------------------------------------------------

        if escaped:

            current.append(char)
            escaped = False
            index += 1
            continue

        if char == "\\" and quote != "'":

            escaped = True
            index += 1
            continue

        # --------------------------------------------------------------
        # QUOTES
        # --------------------------------------------------------------

        if quote:

            if char == quote:
                quote = None
            else:
                current.append(char)

            index += 1
            continue

        if char in {"'", '"'}:

            quote = char
            index += 1
            continue

        # --------------------------------------------------------------
        # WHITESPACE
        # --------------------------------------------------------------

        if char.isspace():

            if current:
                tokens.append("".join(current))
                current = []

            index += 1
            continue

        # --------------------------------------------------------------
        # OPERATORS
        # --------------------------------------------------------------

        matched_operator = None

        for operator in OPERATORS:

            if command.startswith(
                operator,
                index,
            ):
                matched_operator = operator
                break

        if matched_operator:

            if current:
                tokens.append("".join(current))
                current = []

            tokens.append(matched_operator)

            index += len(matched_operator)
            continue

        # --------------------------------------------------------------
        # NORMAL CHARACTER
        # --------------------------------------------------------------

        current.append(char)
        index += 1

    if escaped:
        current.append("\\")

    if quote:
        raise ValueError(
            "Unclosed quote."
        )

    if current:
        tokens.append("".join(current))

    return tokens


# ---------------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------------

def parse_shell(command: str) -> ShellExpression:
    """
    Parse a Convexity shell expression.
    """

    tokens = tokenize_shell(command)

    if not tokens:
        return ShellExpression(
            commands=[],
            operators=[],
        )

    commands: List[ShellCommand] = []
    operators: List[str] = []

    current_tokens: List[str] = []

    stdin_file: Optional[str] = None
    stdout_file: Optional[str] = None
    append_stdout = False
    background = False

    index = 0

    def finish_command() -> None:
        nonlocal current_tokens
        nonlocal stdin_file
        nonlocal stdout_file
        nonlocal append_stdout
        nonlocal background

        if not current_tokens:
            raise ValueError(
                "Missing command."
            )

        commands.append(
            ShellCommand(
                command=" ".join(
                    shlex.quote(token)
                    for token in current_tokens
                ),
                stdin=stdin_file,
                stdout=stdout_file,
                append_stdout=append_stdout,
                background=background,
            )
        )

        current_tokens = []
        stdin_file = None
        stdout_file = None
        append_stdout = False
        background = False

    while index < len(tokens):

        token = tokens[index]

        # --------------------------------------------------------------
        # PIPE / CONDITIONAL OPERATORS
        # --------------------------------------------------------------

        if token in {
            "|",
            "&&",
            "||",
            ";",
        }:

            finish_command()

            operators.append(token)

            index += 1
            continue

        # --------------------------------------------------------------
        # BACKGROUND
        # --------------------------------------------------------------

        if token == "&":

            background = True

            # Background marker normally terminates command.
            finish_command()

            if index + 1 < len(tokens):
                operators.append(";")

            index += 1
            continue

        # --------------------------------------------------------------
        # INPUT REDIRECTION
        # --------------------------------------------------------------

        if token == "<":

            if index + 1 >= len(tokens):
                raise ValueError(
                    "Missing input file after '<'."
                )

            stdin_file = tokens[index + 1]

            index += 2
            continue

        # --------------------------------------------------------------
        # OUTPUT REDIRECTION
        # --------------------------------------------------------------

        if token in {
            ">",
            ">>",
        }:

            if index + 1 >= len(tokens):
                raise ValueError(
                    f"Missing output file after '{token}'."
                )

            stdout_file = tokens[index + 1]

            append_stdout = token == ">>"

            index += 2
            continue

        # --------------------------------------------------------------
        # NORMAL TOKEN
        # --------------------------------------------------------------

        current_tokens.append(token)

        index += 1

    if current_tokens:
        finish_command()

    if len(operators) >= len(commands):
        raise ValueError(
            "Shell expression ends with an operator."
        )

    return ShellExpression(
        commands=commands,
        operators=operators,
    )


# ---------------------------------------------------------------------------
# REDIRECTION
# ---------------------------------------------------------------------------

def _read_stdin(path: str) -> str:

    with open(
        os.path.expanduser(path),
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:

        return file.read()


def _write_stdout(
    path: str,
    output: str,
    *,
    append: bool,
) -> None:

    destination = os.path.expanduser(path)

    parent = os.path.dirname(
        os.path.abspath(destination)
    )

    if parent:
        os.makedirs(
            parent,
            exist_ok=True,
        )

    mode = "a" if append else "w"

    with open(
        destination,
        mode,
        encoding="utf-8",
    ) as file:

        file.write(output)


# ---------------------------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------------------------

class ConvexityShell:
    """Native Convexity shell."""

    def __init__(self) -> None:
        self.environment = dict(os.environ)

    def execute(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:

        try:

            expression = parse_shell(command)

        except ValueError as exc:

            return ExecutionResult(
                success=False,
                stderr=f"Shell syntax error: {exc}",
                return_code=2,
                command=command,
            )

        if not expression.commands:

            return ExecutionResult(
                success=False,
                stderr="Empty command.",
                return_code=2,
                command=command,
            )

        return self._execute_expression(
            expression,
            cwd=cwd,
            source=source,
            confirmed=confirmed,
        )

    # ------------------------------------------------------------------
    # EXPRESSION EXECUTION
    # ------------------------------------------------------------------

    def _execute_expression(
        self,
        expression: ShellExpression,
        *,
        cwd: Optional[str],
        source: str,
        confirmed: bool,
    ) -> ExecutionResult:

        previous_result: Optional[
            ExecutionResult
        ] = None

        for index, shell_command in enumerate(
            expression.commands
        ):

            # ----------------------------------------------------------
            # CONDITIONAL EXECUTION
            # ----------------------------------------------------------

            if (
                previous_result is not None
                and index > 0
            ):

                operator = expression.operators[
                    index - 1
                ]

                if operator == "&&":
                    if not previous_result.success:
                        continue

                elif operator == "||":
                    if previous_result.success:
                        continue

            # ----------------------------------------------------------
            # PIPELINE
            # ----------------------------------------------------------

            if (
                index < len(expression.operators)
                and expression.operators[index] == "|"
            ):

                pipeline_commands = [
                    shell_command.command
                ]

                next_index = index + 1

                while (
                    next_index < len(expression.commands)
                    and next_index - 1 < len(expression.operators)
                    and expression.operators[
                        next_index - 1
                    ] == "|"
                ):

                    pipeline_commands.append(
                        expression.commands[
                            next_index
                        ].command
                    )

                    next_index += 1

                previous_result = execute_pipeline(
                    pipeline_commands,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                )

                continue

            # ----------------------------------------------------------
            # BACKGROUND
            # ----------------------------------------------------------

            if shell_command.background:

                previous_result = start_background(
                    shell_command.command,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                )

                continue

            # ----------------------------------------------------------
            # INPUT
            # ----------------------------------------------------------

            input_data = None

            if shell_command.stdin:

                try:
                    input_data = _read_stdin(
                        shell_command.stdin
                    )

                except OSError as exc:

                    previous_result = ExecutionResult(
                        success=False,
                        stderr=(
                            f"Input redirection error: {exc}"
                        ),
                        return_code=1,
                        command=shell_command.command,
                    )

                    continue

            # ----------------------------------------------------------
            # EXECUTE
            # ----------------------------------------------------------

            previous_result = execute_command(
                shell_command.command,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

            # ----------------------------------------------------------
            # OUTPUT REDIRECTION
            # ----------------------------------------------------------

            if shell_command.stdout:

                try:

                    output = previous_result.stdout

                    _write_stdout(
                        shell_command.stdout,
                        output,
                        append=shell_command.append_stdout,
                    )

                    # Terminal output is consumed by redirection.
                    previous_result.stdout = ""

                except OSError as exc:

                    previous_result.success = False
                    previous_result.return_code = 1
                    previous_result.stderr += (
                        f"\nOutput redirection error: {exc}"
                    )

        return previous_result or ExecutionResult(
            success=False,
            stderr="No command executed.",
            return_code=1,
            command="",
        )


# ---------------------------------------------------------------------------
# GLOBAL SHELL
# ---------------------------------------------------------------------------

shell = ConvexityShell()


def execute_shell(
    command: str,
    *,
    cwd: Optional[str] = None,
    source: str = "human",
    confirmed: bool = False,
) -> ExecutionResult:

    return shell.execute(
        command,
        cwd=cwd,
        source=source,
        confirmed=confirmed,
    )


__all__ = [
    "ShellCommand",
    "ShellExpression",
    "tokenize_shell",
    "parse_shell",
    "ConvexityShell",
    "execute_shell",
]
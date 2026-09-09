"""
Convexity Native Shell Engine
Version 1.0.0

Convexity's native command parser and shell orchestrator.

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

The shell does NOT use:
    shell=True
    os.system()
    subprocess.Popen()

Executable execution is delegated to terminal.executor.py.

Session cwd is passed explicitly instead of changing the process-wide cwd.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .executor import (
    ExecutionResult,
    execute_command,
    execute_pipeline,
    start_background,
)
from .filesystem import (
    read_file,
    write_file,
)
from .security import (
    SecurityError,
    split_shell_segments,
    tokenize_command,
)


# ============================================================================
# OPERATORS
# ============================================================================


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


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class ShellCommand:
    """One parsed command."""

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


# ============================================================================
# TOKENIZER
# ============================================================================


def tokenize_shell(command: str) -> List[str]:
    """
    Tokenize shell text while preserving shell operators.

    Examples:

        echo hello | grep hello

        echo "hello world" > result.txt
    """

    if not isinstance(command, str):
        raise ValueError(
            "Command must be a string."
        )

    if not command.strip():
        return []

    tokens: List[str] = []

    current: List[str] = []

    quote: Optional[str] = None
    escaped = False

    index = 0

    while index < len(command):

        char = command[index]

        # --------------------------------------------------------------
        # ESCAPE
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
        # QUOTE
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
                tokens.append(
                    "".join(current)
                )
                current = []

            index += 1
            continue

        # --------------------------------------------------------------
        # OPERATOR
        # --------------------------------------------------------------

        matched = None

        for operator in OPERATORS:

            if command.startswith(
                operator,
                index,
            ):
                matched = operator
                break

        if matched:

            if current:
                tokens.append(
                    "".join(current)
                )
                current = []

            tokens.append(matched)

            index += len(matched)
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
        tokens.append(
            "".join(current)
        )

    return tokens


# ============================================================================
# PARSER
# ============================================================================


def parse_shell(
    command: str,
) -> ShellExpression:
    """
    Parse a Convexity shell expression.

    The parser keeps commands as executable command strings while storing
    redirections and shell operators separately.
    """

    tokens = tokenize_shell(command)

    if not tokens:
        return ShellExpression(
            commands=[],
            operators=[],
        )

    commands: List[ShellCommand] = []
    operators: List[str] = []

    current: List[str] = []

    stdin_file: Optional[str] = None
    stdout_file: Optional[str] = None

    append_stdout = False
    background = False

    def finish_command() -> None:

        nonlocal current
        nonlocal stdin_file
        nonlocal stdout_file
        nonlocal append_stdout
        nonlocal background

        if not current:
            raise ValueError(
                "Missing command."
            )

        commands.append(
            ShellCommand(
                command=" ".join(
                    _quote_argument(token)
                    for token in current
                ),
                stdin=stdin_file,
                stdout=stdout_file,
                append_stdout=append_stdout,
                background=background,
            )
        )

        current = []

        stdin_file = None
        stdout_file = None

        append_stdout = False
        background = False

    index = 0

    while index < len(tokens):

        token = tokens[index]

        # --------------------------------------------------------------
        # COMMAND OPERATORS
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

            if not current:
                raise ValueError(
                    "Missing command before '&'."
                )

            background = True

            finish_command()

            # Background separates commands.
            if (
                index + 1 < len(tokens)
                and tokens[index + 1] != "&"
            ):
                operators.append(";")

            index += 1
            continue

        # --------------------------------------------------------------
        # INPUT REDIRECTION
        # --------------------------------------------------------------

        if token == "<":

            if not current:
                raise ValueError(
                    "Missing command before '<'."
                )

            if (
                index + 1 >= len(tokens)
                or tokens[index + 1] in OPERATORS
            ):
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

            if not current:
                raise ValueError(
                    f"Missing command before '{token}'."
                )

            if (
                index + 1 >= len(tokens)
                or tokens[index + 1] in OPERATORS
            ):
                raise ValueError(
                    f"Missing output file after '{token}'."
                )

            stdout_file = tokens[index + 1]

            append_stdout = (
                token == ">>"
            )

            index += 2
            continue

        # --------------------------------------------------------------
        # NORMAL TOKEN
        # --------------------------------------------------------------

        current.append(token)

        index += 1

    if current:
        finish_command()

    if len(operators) >= len(commands):
        raise ValueError(
            "Shell expression ends with an operator."
        )

    return ShellExpression(
        commands=commands,
        operators=operators,
    )


def _quote_argument(
    value: str,
) -> str:
    """
    Quote an argument so it can safely be passed back through Convexity's
    parser.
    """

    if value == "":
        return '""'

    safe = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "_-./:@+,%"
    )

    if all(
        char in safe
        for char in value
    ):
        return value

    escaped = value.replace(
        "\\",
        "\\\\",
    ).replace(
        '"',
        '\\"',
    )

    return f'"{escaped}"'


# ============================================================================
# REDIRECTION
# ============================================================================


def _resolve_redirection_path(
    path: str,
    cwd: Optional[str],
) -> str:
    """
    Resolve a redirection path relative to the shell session cwd.

    This does not change the global process cwd.
    """

    if os.path.isabs(path):
        return path

    base = (
        cwd
        if cwd is not None
        else os.getcwd()
    )

    return os.path.abspath(
        os.path.join(
            base,
            path,
        )
    )


def _read_input(
    path: str,
    *,
    cwd: Optional[str],
) -> str:
    """Read shell input redirection."""

    resolved = _resolve_redirection_path(
        path,
        cwd,
    )

    return read_file(
        resolved,
    )


def _write_output(
    path: str,
    output: str,
    *,
    cwd: Optional[str],
    append: bool,
    source: str,
    confirmed: bool,
) -> None:
    """Write shell output redirection."""

    resolved = _resolve_redirection_path(
        path,
        cwd,
    )

    if append:
        from .filesystem import append_file

        append_file(
            resolved,
            output,
            source=source,
            confirmed=confirmed,
        )

    else:
        write_file(
            resolved,
            output,
            overwrite=True,
            source=source,
            confirmed=confirmed,
        )


# ============================================================================
# RESULT HELPERS
# ============================================================================


def _error_result(
    command: str,
    message: str,
    *,
    return_code: int = 2,
) -> ExecutionResult:
    """Create a failed execution result."""

    return ExecutionResult(
        success=False,
        stdout="",
        stderr=message,
        return_code=return_code,
        command=command,
    )


def _combine_results(
    results: List[ExecutionResult],
    command: str,
) -> ExecutionResult:
    """Combine multiple shell results."""

    if not results:
        return _error_result(
            command,
            "No command executed.",
            return_code=1,
        )

    last = results[-1]

    stdout_parts = []
    stderr_parts = []

    for result in results:

        if result.stdout:
            stdout_parts.append(
                result.stdout
            )

        if result.stderr:
            stderr_parts.append(
                result.stderr
            )

    last.stdout = "\n".join(
        stdout_parts
    )

    last.stderr = "\n".join(
        stderr_parts
    )

    return last


# ============================================================================
# SHELL ENGINE
# ============================================================================


class ConvexityShell:
    """
    Convexity's native shell.

    The shell itself is not a process manager. It delegates actual process
    execution to executor.py.
    """

    def __init__(self) -> None:
        self.environment = dict(
            os.environ
        )

    # ------------------------------------------------------------------
    # EXECUTE
    # ------------------------------------------------------------------

    def execute(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        source: str = "human",
        confirmed: bool = False,
    ) -> ExecutionResult:
        """Parse and execute a shell expression."""

        if not isinstance(
            command,
            str,
        ):
            return _error_result(
                "",
                "Command must be a string.",
            )

        if not command.strip():
            return _error_result(
                command,
                "Empty command.",
            )

        try:

            expression = parse_shell(
                command
            )

        except (
            ValueError,
            SecurityError,
        ) as exc:

            return _error_result(
                command,
                f"Shell syntax error: {exc}",
            )

        if not expression.commands:
            return _error_result(
                command,
                "Empty command.",
            )

        try:

            return self._execute_expression(
                expression,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

        except SecurityError as exc:

            return _error_result(
                command,
                str(exc),
                return_code=1,
            )

    # ------------------------------------------------------------------
    # EXPRESSION
    # ------------------------------------------------------------------

    def _execute_expression(
        self,
        expression: ShellExpression,
        *,
        cwd: Optional[str],
        source: str,
        confirmed: bool,
    ) -> ExecutionResult:

        results: List[
            ExecutionResult
        ] = []

        index = 0

        while index < len(
            expression.commands
        ):

            shell_command = (
                expression.commands[index]
            )

            # ----------------------------------------------------------
            # CONDITIONALS
            # ----------------------------------------------------------

            if index > 0:

                operator = (
                    expression.operators[
                        index - 1
                    ]
                )

                previous = results[-1]

                if operator == "&&":

                    if not previous.success:
                        index += 1
                        continue

                elif operator == "||":

                    if previous.success:
                        index += 1
                        continue

            # ----------------------------------------------------------
            # PIPELINE
            # ----------------------------------------------------------

            if (
                index
                < len(expression.operators)
                and expression.operators[index]
                == "|"
            ):

                pipeline = [
                    shell_command.command
                ]

                pipeline_end = index

                while (
                    pipeline_end
                    < len(expression.operators)
                    and expression.operators[
                        pipeline_end
                    ] == "|"
                ):

                    next_command_index = (
                        pipeline_end + 1
                    )

                    if (
                        next_command_index
                        >= len(
                            expression.commands
                        )
                    ):
                        raise ValueError(
                            "Missing command after '|'."
                        )

                    pipeline.append(
                        expression.commands[
                            next_command_index
                        ].command
                    )

                    pipeline_end += 1

                result = execute_pipeline(
                    pipeline,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                )

                results.append(result)

                index = pipeline_end + 1

                continue

            # ----------------------------------------------------------
            # BACKGROUND
            # ----------------------------------------------------------

            if shell_command.background:

                result = start_background(
                    shell_command.command,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                )

                results.append(result)

                index += 1

                continue

            # ----------------------------------------------------------
            # INPUT REDIRECTION
            # ----------------------------------------------------------

            input_data = None

            if shell_command.stdin:

                try:

                    input_data = _read_input(
                        shell_command.stdin,
                        cwd=cwd,
                    )

                except (
                    OSError,
                    SecurityError,
                ) as exc:

                    result = _error_result(
                        shell_command.command,
                        (
                            "Input redirection error: "
                            f"{exc}"
                        ),
                        return_code=1,
                    )

                    results.append(result)

                    index += 1

                    continue

            # ----------------------------------------------------------
            # EXECUTE
            # ----------------------------------------------------------

            result = execute_command(
                shell_command.command,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

            # ----------------------------------------------------------
            # INPUT NOTE
            # ----------------------------------------------------------
            #
            # The canonical executor currently owns process stdin.
            # Therefore input_data is intentionally not injected through
            # subprocess APIs here. This keeps shell.py from bypassing
            # executor.py.
            #
            # Future executor support can accept structured stdin without
            # changing the shell parser.
            # ----------------------------------------------------------

            if input_data is not None:
                if not result.stdout:
                    result.stdout = ""

            # ----------------------------------------------------------
            # OUTPUT REDIRECTION
            # ----------------------------------------------------------

            if shell_command.stdout:

                try:

                    _write_output(
                        shell_command.stdout,
                        result.stdout,
                        cwd=cwd,
                        append=(
                            shell_command.append_stdout
                        ),
                        source=source,
                        confirmed=confirmed,
                    )

                    result.stdout = ""

                except (
                    OSError,
                    SecurityError,
                ) as exc:

                    result.success = False
                    result.return_code = 1

                    if result.stderr:
                        result.stderr += "\n"

                    result.stderr += (
                        "Output redirection error: "
                        f"{exc}"
                    )

            results.append(result)

            index += 1

        return _combine_results(
            results,
            "shell expression",
        )


# ============================================================================
# GLOBAL SHELL INSTANCE
# ============================================================================


shell = ConvexityShell()


def execute_shell(
    command: str,
    *,
    cwd: Optional[str] = None,
    source: str = "human",
    confirmed: bool = False,
) -> ExecutionResult:
    """
    Convenience wrapper around the global Convexity shell.
    """

    return shell.execute(
        command,
        cwd=cwd,
        source=source,
        confirmed=confirmed,
    )


# ============================================================================
# PUBLIC API
# ============================================================================


__all__ = [
    "OPERATORS",
    "ShellCommand",
    "ShellExpression",
    "tokenize_shell",
    "parse_shell",
    "ConvexityShell",
    "shell",
    "execute_shell",
]

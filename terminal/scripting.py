"""
Convexity Native Scripting Engine
Version 0.6.0

Convexity's native script runner.

Script extension:
    .cvx

Supported initially:
    - commands
    - comments
    - variables
    - variable expansion
    - if / else
    - while
    - repeat
    - functions
    - return
    - exit
    - simple command arguments

Example:

    set PROJECT Maple
    mkdir $PROJECT
    cd $PROJECT

    if exists(model.gguf)
        echo Model exists
    else
        echo Model missing
    end

    repeat 3
        echo Training step
    end

This interpreter is intentionally independent of Bash,
PowerShell, CMD and Termux.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from .environment import (
    ShellContext,
    context as global_context,
)

from .builtins import (
    execute_builtin,
    is_builtin,
)

from .shell import execute_shell


# ---------------------------------------------------------------------------
# SCRIPT RESULT
# ---------------------------------------------------------------------------

@dataclass
class ScriptResult:

    success: bool

    stdout: str = ""

    stderr: str = ""

    return_code: int = 0

    lines_executed: int = 0


# ---------------------------------------------------------------------------
# SCRIPT FUNCTION
# ---------------------------------------------------------------------------

@dataclass
class ScriptFunction:

    name: str

    arguments: list[str]

    body: list[str] = field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# CONTROL SIGNAL
# ---------------------------------------------------------------------------

@dataclass
class ControlSignal:

    kind: str

    value: Optional[int] = None


# ---------------------------------------------------------------------------
# SCRIPT ENGINE
# ---------------------------------------------------------------------------

class ConvexityScriptEngine:

    def __init__(
        self,
        shell_context: Optional[
            ShellContext
        ] = None,
    ) -> None:

        self.context = (
            shell_context
            if shell_context is not None
            else global_context
        )

        self.functions: dict[
            str,
            ScriptFunction
        ] = {}

        self.max_loop_iterations = 10000

        self.max_call_depth = 32

        self.call_depth = 0

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------

    def load_file(
        self,
        path: str,
    ) -> list[str]:

        path = os.path.expanduser(path)

        with open(
            path,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as file:

            return file.readlines()

    # ------------------------------------------------------------------
    # RUN FILE
    # ------------------------------------------------------------------

    def run_file(
        self,
        path: str,
        *,
        cwd: Optional[str] = None,
        source: str = "script",
        confirmed: bool = False,
    ) -> ScriptResult:

        try:

            lines = self.load_file(path)

        except OSError as exc:

            return ScriptResult(
                success=False,
                stderr=(
                    f"Cannot read script: {exc}\n"
                ),
                return_code=1,
            )

        return self.run(
            lines,
            cwd=cwd,
            source=source,
            confirmed=confirmed,
        )

    # ------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------

    def run(
        self,
        lines: list[str],
        *,
        cwd: Optional[str] = None,
        source: str = "script",
        confirmed: bool = False,
    ) -> ScriptResult:

        output: list[str] = []

        errors: list[str] = []

        self.functions = {}

        cleaned = self._clean_lines(
            lines
        )

        self._collect_functions(
            cleaned
        )

        result = self._execute_block(
            cleaned,
            cwd=cwd,
            source=source,
            confirmed=confirmed,
            output=output,
            errors=errors,
        )

        if result is None:

            return ScriptResult(
                success=True,
                stdout="".join(output),
                stderr="".join(errors),
                return_code=0,
                lines_executed=len(cleaned),
            )

        return ScriptResult(
            success=result.success,
            stdout="".join(output),
            stderr="".join(errors),
            return_code=result.return_code,
            lines_executed=len(cleaned),
        )

    # ------------------------------------------------------------------
    # CLEAN
    # ------------------------------------------------------------------

    def _clean_lines(
        self,
        lines: list[str],
    ) -> list[str]:

        cleaned = []

        for raw in lines:

            line = raw.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            cleaned.append(line)

        return cleaned

    # ------------------------------------------------------------------
    # FUNCTIONS
    # ------------------------------------------------------------------

    def _collect_functions(
        self,
        lines: list[str],
    ) -> None:

        index = 0

        while index < len(lines):

            line = lines[index]

            if line.startswith("function "):

                header = line[
                    len("function "):
                ].strip()

                name, arguments = (
                    self._parse_function_header(
                        header
                    )
                )

                body: list[str] = []

                index += 1

                while (
                    index < len(lines)
                    and lines[index].lower()
                    != "end"
                ):

                    body.append(
                        lines[index]
                    )

                    index += 1

                self.functions[name] = (
                    ScriptFunction(
                        name=name,
                        arguments=arguments,
                        body=body,
                    )
                )

            index += 1

    def _parse_function_header(
        self,
        header: str,
    ) -> tuple[str, list[str]]:

        match = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*)"
            r"(?:\s*\((.*?)\))?$",
            header,
        )

        if not match:

            raise ValueError(
                f"Invalid function declaration: {header}"
            )

        name = match.group(1)

        argument_text = (
            match.group(2) or ""
        ).strip()

        if not argument_text:

            arguments = []

        else:

            arguments = [
                item.strip()
                for item in argument_text.split(",")
                if item.strip()
            ]

        return name, arguments

    # ------------------------------------------------------------------
    # BLOCK EXECUTION
    # ------------------------------------------------------------------

    def _execute_block(
        self,
        lines: list[str],
        *,
        cwd: Optional[str],
        source: str,
        confirmed: bool,
        output: list[str],
        errors: list[str],
    ) -> Optional[ScriptResult]:

        index = 0

        while index < len(lines):

            line = lines[index]

            lower = line.lower()

            # ----------------------------------------------------------
            # FUNCTION DECLARATIONS
            # ----------------------------------------------------------

            if lower.startswith("function "):

                index = self._skip_block(
                    lines,
                    index,
                )

                index += 1

                continue

            # ----------------------------------------------------------
            # IF
            # ----------------------------------------------------------

            if lower.startswith("if "):

                end_index = self._find_matching_end(
                    lines,
                    index,
                )

                if end_index is None:

                    return ScriptResult(
                        success=False,
                        stderr=(
                            "if: missing end\n"
                        ),
                        return_code=2,
                    )

                block = lines[
                    index + 1:end_index
                ]

                else_index = self._find_else(
                    block
                )

                condition_text = line[
                    3:
                ].strip()

                condition = self._evaluate_condition(
                    condition_text,
                    cwd=cwd,
                )

                if condition:

                    selected = (
                        block[:else_index]
                        if else_index is not None
                        else block
                    )

                else:

                    selected = (
                        block[else_index + 1:]
                        if else_index is not None
                        else []
                    )

                result = self._execute_block(
                    selected,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                    output=output,
                    errors=errors,
                )

                if result is not None:

                    if result.return_code != 0:
                        return result

                index = end_index + 1

                continue

            # ----------------------------------------------------------
            # WHILE
            # ----------------------------------------------------------

            if lower.startswith("while "):

                end_index = self._find_matching_end(
                    lines,
                    index,
                )

                if end_index is None:

                    return ScriptResult(
                        success=False,
                        stderr=(
                            "while: missing end\n"
                        ),
                        return_code=2,
                    )

                block = lines[
                    index + 1:end_index
                ]

                condition_text = line[
                    6:
                ].strip()

                iterations = 0

                while self._evaluate_condition(
                    condition_text,
                    cwd=cwd,
                ):

                    iterations += 1

                    if (
                        iterations
                        > self.max_loop_iterations
                    ):

                        return ScriptResult(
                            success=False,
                            stderr=(
                                "while: maximum "
                                "iterations exceeded\n"
                            ),
                            return_code=1,
                        )

                    result = self._execute_block(
                        block,
                        cwd=cwd,
                        source=source,
                        confirmed=confirmed,
                        output=output,
                        errors=errors,
                    )

                    if result is not None:

                        if result.return_code != 0:
                            return result

                index = end_index + 1

                continue

            # ----------------------------------------------------------
            # REPEAT
            # ----------------------------------------------------------

            if lower.startswith("repeat "):

                end_index = self._find_matching_end(
                    lines,
                    index,
                )

                if end_index is None:

                    return ScriptResult(
                        success=False,
                        stderr=(
                            "repeat: missing end\n"
                        ),
                        return_code=2,
                    )

                block = lines[
                    index + 1:end_index
                ]

                count_text = line[
                    7:
                ].strip()

                count_text = self.context.expand(
                    count_text
                )

                try:

                    count = int(
                        count_text
                    )

                except ValueError:

                    return ScriptResult(
                        success=False,
                        stderr=(
                            "repeat: invalid count\n"
                        ),
                        return_code=2,
                    )

                if count < 0:
                    count = 0

                if (
                    count
                    > self.max_loop_iterations
                ):

                    return ScriptResult(
                        success=False,
                        stderr=(
                            "repeat: count exceeds limit\n"
                        ),
                        return_code=1,
                    )

                for iteration in range(
                    count
                ):

                    self.context.environment.set(
                        "INDEX",
                        str(iteration),
                    )

                    result = self._execute_block(
                        block,
                        cwd=cwd,
                        source=source,
                        confirmed=confirmed,
                        output=output,
                        errors=errors,
                    )

                    if result is not None:

                        if result.return_code != 0:
                            return result

                index = end_index + 1

                continue

            # ----------------------------------------------------------
            # RETURN
            # ----------------------------------------------------------

            if lower == "return":

                return ScriptResult(
                    success=True,
                    stdout="".join(output),
                    stderr="".join(errors),
                    return_code=0,
                )

            if lower.startswith("return "):

                value = self.context.expand(
                    line[7:].strip()
                )

                try:
                    code = int(value)
                except ValueError:
                    code = 0

                return ScriptResult(
                    success=code == 0,
                    stdout="".join(output),
                    stderr="".join(errors),
                    return_code=code,
                )

            # ----------------------------------------------------------
            # EXIT
            # ----------------------------------------------------------

            if lower == "exit":

                return ScriptResult(
                    success=True,
                    stdout="".join(output),
                    stderr="".join(errors),
                    return_code=0,
                )

            if lower.startswith("exit "):

                value = self.context.expand(
                    line[5:].strip()
                )

                try:
                    code = int(value)
                except ValueError:
                    code = 0

                return ScriptResult(
                    success=code == 0,
                    stdout="".join(output),
                    stderr="".join(errors),
                    return_code=code,
                )

            # ----------------------------------------------------------
            # COMMAND
            # ----------------------------------------------------------

            command = self.context.expand(
                line
            )

            command = self.context.environment.expand_alias(
                command
            )

            result = self._execute_command(
                command,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

            if result.stdout:
                output.append(
                    result.stdout
                )

            if result.stderr:
                errors.append(
                    result.stderr
                )

            self.context.update_result(
                command,
                result.return_code,
            )

            if not result.success:

                return ScriptResult(
                    success=False,
                    stdout="".join(output),
                    stderr="".join(errors),
                    return_code=result.return_code,
                )

            index += 1

        return None

    # ------------------------------------------------------------------
    # COMMAND EXECUTION
    # ------------------------------------------------------------------

    def _execute_command(
        self,
        command: str,
        *,
        cwd: Optional[str],
        source: str,
        confirmed: bool,
    ):

        try:

            parts = re.split(
                r"\s+",
                command.strip(),
                maxsplit=1,
            )

            name = parts[0]

            argument_text = (
                parts[1]
                if len(parts) > 1
                else ""
            )

            try:

                import shlex

                arguments = shlex.split(
                    argument_text
                )

            except ValueError:

                return execute_shell(
                    command,
                    cwd=cwd,
                    source=source,
                    confirmed=confirmed,
                )

            if is_builtin(name):

                return self._builtin_adapter(
                    name,
                    arguments,
                    cwd=cwd,
                    confirmed=confirmed,
                )

            return execute_shell(
                command,
                cwd=cwd,
                source=source,
                confirmed=confirmed,
            )

        except Exception as exc:

            from .executor import ExecutionResult

            return ExecutionResult(
                success=False,
                stderr=(
                    f"Script command error: {exc}\n"
                ),
                return_code=1,
                command=command,
            )

    # ------------------------------------------------------------------
    # BUILTIN ADAPTER
    # ------------------------------------------------------------------

    def _builtin_adapter(
        self,
        name: str,
        arguments: list[str],
        *,
        cwd: Optional[str],
        confirmed: bool,
    ):

        from .executor import ExecutionResult

        result = execute_builtin(
            name,
            arguments,
            cwd=cwd,
            confirmed=confirmed,
            context=self.context,
        )

        return
"""
Convexity Terminal
Version 0.2.0

Main interactive shell for Convexity.

Architecture:

    User
      ↓
    Convexity Terminal
      ↓
    Command Parser
      ↓
    Security Layer
      ↓
    Executor / Filesystem
      ↓
    Operating System
"""

from __future__ import annotations

import os
import readline
import shlex
import sys
from pathlib import Path
from typing import Optional

from .config import config
from .executor import (
    execute_command,
    execute_pipeline,
    start_background,
    list_processes,
    terminate_process,
    kill_process,
)
from .filesystem import (
    get_current_directory,
    list_directory,
    change_directory,
    make_directory,
    touch_file,
    read_file,
    write_file,
    append_file,
    delete_path,
    copy_path,
    move_path,
    rename_path,
    search_files,
    find_text,
    get_file_info,
    get_file_size,
    get_directory_size,
    exists,
)
from .security import SecurityError, PermissionDenied


class ConvexityTerminal:
    """Main Convexity terminal interface."""

    def __init__(self) -> None:
        self.running = False
        self.version = config.VERSION
        self.history_file = config.get_history_path()

        self._setup_history()

    # ------------------------------------------------------------------
    # START
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the interactive Convexity terminal."""

        self.running = True

        self._print_banner()

        while self.running:

            try:
                prompt = self._build_prompt()

                command = input(prompt)

                command = command.strip()

                if not command:
                    continue

                self.process_command(command)

            except KeyboardInterrupt:
                print("\nUse 'exit' to leave Convexity.")

            except EOFError:
                print()
                self.running = False

            except Exception as exc:
                print(f"Convexity error: {exc}")

        self._save_history()

    # ------------------------------------------------------------------
    # COMMAND PROCESSING
    # ------------------------------------------------------------------

    def process_command(self, command_str: str) -> None:
        """Process a single command."""

        command_str = command_str.strip()

        if not command_str:
            return

        try:
            tokens = shlex.split(
                command_str,
                posix=(os.name != "nt"),
            )

        except ValueError as exc:
            print(f"Syntax error: {exc}")
            return

        if not tokens:
            return

        command = tokens[0].lower()
        args = tokens[1:]

        # --------------------------------------------------------------
        # SHELL CONTROL
        # --------------------------------------------------------------

        if command in {"exit", "quit"}:
            self.running = False
            print("Goodbye.")
            return

        if command == "help":
            self.show_help()
            return

        if command == "clear":
            self.clear()
            return

        if command == "version":
            print(
                f"{config.APP_NAME} "
                f"{config.VERSION}"
            )
            return

        # --------------------------------------------------------------
        # DIRECTORY
        # --------------------------------------------------------------

        if command in {"pwd", "cwd"}:
            print(get_current_directory())
            return

        if command in {"cd", "chdir"}:
            self.command_cd(args)
            return

        if command in {"ls", "dir"}:
            self.command_ls(args)
            return

        # --------------------------------------------------------------
        # FILESYSTEM
        # --------------------------------------------------------------

        if command == "mkdir":
            self.command_mkdir(args)
            return

        if command == "touch":
            self.command_touch(args)
            return

        if command in {"cat", "read"}:
            self.command_cat(args)
            return

        if command in {"write", "set-content"}:
            self.command_write(args)
            return

        if command in {"append", "add-content"}:
            self.command_append(args)
            return

        if command in {"rm", "del", "delete"}:
            self.command_rm(args)
            return

        if command in {"cp", "copy"}:
            self.command_copy(args)
            return

        if command in {"mv", "move"}:
            self.command_move(args)
            return

        if command == "rename":
            self.command_rename(args)
            return

        if command in {"exists", "test-path"}:
            self.command_exists(args)
            return

        if command in {"stat", "info"}:
            self.command_info(args)
            return

        if command in {"size", "du"}:
            self.command_size(args)
            return

        if command in {"find", "search"}:
            self.command_find(args)
            return

        if command in {"grep", "findtext"}:
            self.command_grep(args)
            return

        # --------------------------------------------------------------
        # PROCESS MANAGEMENT
        # --------------------------------------------------------------

        if command in {"jobs", "ps"}:
            self.command_processes()
            return

        if command in {"kill", "stop"}:
            self.command_kill(args)
            return

        if command in {"bg", "background"}:
            self.command_background(args)
            return

        # --------------------------------------------------------------
        # ENVIRONMENT
        # --------------------------------------------------------------

        if command in {"env", "environment"}:
            self.command_env()
            return

        if command == "set":
            self.command_set(args)
            return

        if command == "unset":
            self.command_unset(args)
            return

        # --------------------------------------------------------------
        # SHELL OPERATORS
        # --------------------------------------------------------------

        if self._contains_shell_operator(command_str):
            self.command_shell(command_str)
            return

        # --------------------------------------------------------------
        # EXTERNAL COMMAND
        # --------------------------------------------------------------

        self.command_external(command_str)

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------

    def show_help(self) -> None:
        print(
            """
Convexity Terminal
==================

Navigation:
  pwd                         Show current directory
  cd <path>                   Change directory
  ls [path]                   List directory
  dir [path]                  Alias for ls

Files:
  mkdir <path>                Create directory
  touch <file>                Create file
  cat <file>                  Read file
  write <file> <text>         Write file
  append <file> <text>        Append to file
  rm <path>                   Delete
  cp <src> <dst>              Copy
  mv <src> <dst>              Move
  rename <path> <name>        Rename

Search:
  find <path> <pattern>       Find files
  grep <path> <text>          Search text
  exists <path>               Check path
  stat <path>                 File information
  size <path>                 Size

Processes:
  ps                          List Convexity processes
  jobs                        List background processes
  bg <command>                Start background process
  kill <pid>                  Terminate process

Environment:
  env                         Show environment
  set <name> <value>          Set environment variable
  unset <name>                Remove variable

Shell:
  command1 | command2         Pipeline
  command1 > file             Redirection (shell engine)
  command1 >> file            Append redirection
  command1 && command2        Conditional execution
  command1 || command2        Conditional fallback

System:
  help                        Show this help
  clear                       Clear terminal
  version                     Show version
  exit                        Exit Convexity

Any external executable available to Convexity's runtime can be passed
to the execution engine.
"""
        )

    # ------------------------------------------------------------------
    # DIRECTORY COMMANDS
    # ------------------------------------------------------------------

    def command_cd(self, args: list[str]) -> None:

        if not args:
            target = Path.home()
        else:
            target = args[0]

        try:
            result = change_directory(target)
            print(result)

        except SecurityError as exc:
            print(f"cd: {exc}")

    def command_ls(self, args: list[str]) -> None:

        path = "."
        show_hidden = False
        recursive = False

        for arg in args:

            if arg in {"-a", "--all"}:
                show_hidden = True

            elif arg in {"-r", "--recursive"}:
                recursive = True

            elif not arg.startswith("-"):
                path = arg

        try:
            entries = list_directory(
                path,
                show_hidden=show_hidden,
                recursive=recursive,
            )

            for entry in entries:

                marker = (
                    "<DIR>"
                    if entry.is_directory
                    else "     "
                )

                print(
                    f"{marker:5} "
                    f"{entry.size:>10} "
                    f"{entry.name}"
                )

        except SecurityError as exc:
            print(f"ls: {exc}")

    # ------------------------------------------------------------------
    # FILE COMMANDS
    # ------------------------------------------------------------------

    def command_mkdir(self, args: list[str]) -> None:

        if not args:
            print("Usage: mkdir <path>")
            return

        try:
            for path in args:
                result = make_directory(path)
                print(f"Created: {result}")

        except Exception as exc:
            print(f"mkdir: {exc}")

    def command_touch(self, args: list[str]) -> None:

        if not args:
            print("Usage: touch <file>")
            return

        try:
            for path in args:
                result = touch_file(path)
                print(f"Created: {result}")

        except Exception as exc:
            print(f"touch: {exc}")

    def command_cat(self, args: list[str]) -> None:

        if not args:
            print("Usage: cat <file>")
            return

        try:
            for path in args:
                print(read_file(path))

        except Exception as exc:
            print(f"cat: {exc}")

    def command_write(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: write <file> <text>")
            return

        path = args[0]
        content = " ".join(args[1:])

        confirmed = self._confirm(
            f"Overwrite '{path}' if it already exists?"
        )

        try:
            result = write_file(
                path,
                content,
                confirmed=confirmed,
            )

            print(f"Written: {result}")

        except Exception as exc:
            print(f"write: {exc}")

    def command_append(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: append <file> <text>")
            return

        path = args[0]
        content = " ".join(args[1:])

        try:
            result = append_file(
                path,
                content,
                confirmed=self._confirm(
                    f"Append to '{path}'?"
                ),
            )

            print(f"Updated: {result}")

        except Exception as exc:
            print(f"append: {exc}")

    def command_rm(self, args: list[str]) -> None:

        if not args:
            print("Usage: rm <path> [--recursive]")
            return

        recursive = False
        paths = []

        for arg in args:

            if arg in {"-r", "-R", "--recursive"}:
                recursive = True
            else:
                paths.append(arg)

        if not paths:
            print("Usage: rm <path>")
            return

        for path in paths:

            confirmed = self._confirm(
                f"Delete '{path}'"
                + (" recursively?" if recursive else "?")
            )

            if not confirmed:
                print("Cancelled.")
                continue

            try:
                result = delete_path(
                    path,
                    recursive=recursive,
                    confirmed=True,
                )

                if result:
                    print(f"Deleted: {path}")
                else:
                    print(f"Not found: {path}")

            except Exception as exc:
                print(f"rm: {exc}")

    def command_copy(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: cp <source> <destination>")
            return

        try:
            result = copy_path(
                args[0],
                args[1],
                overwrite=False,
            )

            print(f"Copied to: {result}")

        except Exception as exc:
            print(f"cp: {exc}")

    def command_move(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: mv <source> <destination>")
            return

        try:
            result = move_path(
                args[0],
                args[1],
                overwrite=False,
            )

            print(f"Moved to: {result}")

        except Exception as exc:
            print(f"mv: {exc}")

    def command_rename(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: rename <path> <new-name>")
            return

        try:
            result = rename_path(
                args[0],
                args[1],
                confirmed=self._confirm(
                    f"Rename '{args[0]}'?"
                ),
            )

            print(f"Renamed to: {result}")

        except Exception as exc:
            print(f"rename: {exc}")

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------

    def command_find(self, args: list[str]) -> None:

        if not args:
            print("Usage: find <path> [pattern]")
            return

        path = args[0]
        pattern = args[1] if len(args) > 1 else "*"

        try:
            results = search_files(
                path,
                pattern,
            )

            for result in results:
                print(result)

            print(f"\n{len(results)} result(s).")

        except Exception as exc:
            print(f"find: {exc}")

    def command_grep(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: grep <path> <text>")
            return

        path = args[0]
        text = " ".join(args[1:])

        try:
            results = find_text(
                path,
                text,
            )

            for file_path, line, content in results:
                print(
                    f"{file_path}:{line}: {content}"
                )

            print(f"\n{len(results)} match(es).")

        except Exception as exc:
            print(f"grep: {exc}")

    # ------------------------------------------------------------------
    # INFORMATION
    # ------------------------------------------------------------------

    def command_exists(self, args: list[str]) -> None:

        if not args:
            print("Usage: exists <path>")
            return

        for path in args:
            print(
                f"{path}: "
                f"{'True' if exists(path) else 'False'}"
            )

    def command_info(self, args: list[str]) -> None:

        if not args:
            print("Usage: stat <path>")
            return

        try:
            info = get_file_info(args[0])

            print(f"Path:        {info.path}")
            print(f"Name:        {info.name}")
            print(f"Type:        {info.type}")
            print(f"Size:        {info.size} bytes")
            print(f"Permissions: {info.permissions}")
            print(f"Modified:    {info.modified}")
            print(f"Hidden:      {info.hidden}")

        except Exception as exc:
            print(f"stat: {exc}")

    def command_size(self, args: list[str]) -> None:

        if not args:
            print("Usage: size <path>")
            return

        try:
            print(
                f"{get_directory_size(args[0]):,} bytes"
            )

        except Exception as exc:
            print(f"size: {exc}")

    # ------------------------------------------------------------------
    # PROCESSES
    # ------------------------------------------------------------------

    def command_processes(self) -> None:

        processes = list_processes()

        if not processes:
            print("No Convexity background processes.")
            return

        for process in processes:

            status = (
                "running"
                if process.running
                else f"exit={process.return_code}"
            )

            print(
                f"{process.pid:<8} "
                f"{status:<12} "
                f"{process.command}"
            )

    def command_background(self, args: list[str]) -> None:

        if not args:
            print("Usage: bg <command>")
            return

        command = " ".join(
            shlex.quote(arg)
            for arg in args
        )

        result = start_background(command)

        print(result.stdout or result.stderr)

    def command_kill(self, args: list[str]) -> None:

        if not args:
            print("Usage: kill <pid>")
            return

        try:
            pid = int(args[0])

        except ValueError:
            print("kill: PID must be a number.")
            return

        if not self._confirm(
            f"Terminate process {pid}?"
        ):
            print("Cancelled.")
            return

        if terminate_process(pid):
            print(f"Process {pid} terminated.")
        else:
            print(f"Unable to terminate process {pid}.")

    # ------------------------------------------------------------------
    # ENVIRONMENT
    # ------------------------------------------------------------------

    def command_env(self) -> None:

        for key in sorted(os.environ):
            print(
                f"{key}={os.environ[key]}"
            )

    def command_set(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: set <name> <value>")
            return

        name = args[0]
        value = " ".join(args[1:])

        os.environ[name] = value

        print(
            f"{name}={value}"
        )

    def command_unset(self, args: list[str]) -> None:

        if not args:
            print("Usage: unset <name>")
            return

        for name in args:
            os.environ.pop(
                name,
                None,
            )

    # ------------------------------------------------------------------
    # EXTERNAL COM
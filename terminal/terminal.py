"""
Convexity Terminal
Version: 1.0.1

Interactive user-facing terminal interface.

Architecture:

    User
      ↓
    Terminal
      ↓
    TerminalRuntime
      ↓
    Session
      ↓
    Executor
      ↓
    Operating System

Maple is optional. When loaded, Maple can analyze and
authorize actions, but manual terminal usage remains available.
"""

from __future__ import annotations

import os
import platform
import shlex
import sys
from typing import Optional

from .runtime import TerminalRuntime, get_runtime
from .session import TerminalSession


__version__ = "1.0.1"


class ConvexityTerminal:
    """
    Main interactive Convexity terminal.
    """

    def __init__(
        self,
        *,
        runtime: Optional[TerminalRuntime] = None,
        session: Optional[TerminalSession] = None,
    ) -> None:

        self.runtime = runtime or get_runtime()

        if session is None:
            sessions = self.runtime.list_sessions()

            if sessions:
                self.session = sessions[0]
            else:
                self.session = self.runtime.create_session()

        else:
            self.session = session

        self.running = True

    # ========================================================
    # PROPERTIES
    # ========================================================

    @property
    def session_id(self) -> str:
        return self.session.session_id

    @property
    def cwd(self) -> str:
        return self.session.cwd

    # ========================================================
    # PROMPT
    # ========================================================

    def build_prompt(self) -> str:
        """
        Build the terminal prompt.
        """

        maple_state = ""

        try:
            if self.session.is_maple_loaded():
                maple_state = " [Maple]"
        except AttributeError:
            pass

        directory = self.cwd

        try:
            home = os.path.expanduser("~")

            if directory.startswith(home):
                directory = "~" + directory[len(home):]

        except Exception:
            pass

        return f"convexity:{directory}{maple_state}> "

    # ========================================================
    # MAIN LOOP
    # ========================================================

    def run(self) -> None:
        """
        Start the interactive terminal.
        """

        self.running = True

        self.print_banner()

        while self.running:

            try:
                command = input(self.build_prompt())

            except EOFError:
                print()
                break

            except KeyboardInterrupt:
                print()
                continue

            command = command.strip()

            if not command:
                continue

            try:
                self.handle_command(command)

            except KeyboardInterrupt:
                print("^C")

            except Exception as exc:
                print(f"convexity: error: {exc}")

    # ========================================================
    # BANNER
    # ========================================================

    def print_banner(self) -> None:
        print()
        print("Convexity Terminal")
        print(f"Version {__version__}")
        print(f"Platform: {platform.system()}")
        print("Type 'help' for commands.")
        print()

    # ========================================================
    # COMMAND DISPATCH
    # ========================================================

    def handle_command(self, command: str) -> None:
        """
        Dispatch a command.
        """

        try:
            parts = shlex.split(command)

        except ValueError as exc:
            print(f"parse error: {exc}")
            return

        if not parts:
            return

        name = parts[0].lower()
        args = parts[1:]

        # ----------------------------------------------------
        # Terminal control
        # ----------------------------------------------------

        if name in {"exit", "quit"}:
            self.command_exit()
            return

        if name == "help":
            self.command_help()
            return

        if name == "clear":
            self.command_clear()
            return

        # ----------------------------------------------------
        # Session
        # ----------------------------------------------------

        if name == "pwd":
            self.command_pwd()
            return

        if name == "cd":
            self.command_cd(args)
            return

        if name in {"history", "hist"}:
            self.command_history(args)
            return

        # ----------------------------------------------------
        # Environment
        # ----------------------------------------------------

        if name == "env":
            self.command_env()
            return

        if name == "set":
            self.command_set(args)
            return

        if name == "unset":
            self.command_unset(args)
            return

        # ----------------------------------------------------
        # Maple state
        # ----------------------------------------------------

        if name == "load" and args and args[0].lower() == "maple":
            self.command_load_maple()
            return

        if name == "kill" and args and args[0].lower() == "maple":
            self.command_kill_maple()
            return

        # ----------------------------------------------------
        # System
        # ----------------------------------------------------

        if name == "whoami":
            self.command_external(command)
            return

        if name == "hostname":
            self.command_external(command)
            return

        if name in {"sysinfo", "systeminfo"}:
            self.command_sysinfo()
            return

        # ----------------------------------------------------
        # Jobs/processes
        # ----------------------------------------------------

        if name in {"jobs", "ps"}:
            self.command_processes()
            return

        # ----------------------------------------------------
        # Everything else
        # ----------------------------------------------------

        self.command_external(command)

    # ========================================================
    # HELP
    # ========================================================

    def command_help(self) -> None:
        print(
            """
Convexity Terminal Commands
----------------------------

Terminal:
  help                 Show this help
  clear                Clear the screen
  exit                 Exit Convexity

Navigation:
  pwd                  Show current directory
  cd <path>            Change directory

Environment:
  env                  Show environment variables
  set <name> <value>   Set a variable
  unset <name>         Remove a variable

History:
  history              Show command history

Processes:
  jobs                 Show active jobs
  ps                   Show processes

Maple:
  load maple           Activate Maple
  kill maple           Deactivate Maple

System:
  whoami               Current user
  hostname             Computer name
  sysinfo              System information

External commands:
  Any supported system command can be entered directly.

Examples:
  python script.py
  git status
  npm install
  ls
  cd projects
  load maple
  kill maple
"""
        )

    # ========================================================
    # EXIT
    # ========================================================

    def command_exit(self) -> None:
        self.running = False

    # ========================================================
    # CLEAR
    # ========================================================

    def command_clear(self) -> None:
        os.system("cls" if os.name == "nt" else "clear")

    # ========================================================
    # PWD
    # ========================================================

    def command_pwd(self) -> None:
        print(self.session.cwd)

    # ========================================================
    # CD
    # ========================================================

    def command_cd(self, args: list[str]) -> None:

        if not args:
            target = os.path.expanduser("~")
        else:
            target = args[0]

        if not os.path.isabs(target):
            target = os.path.join(
                self.session.cwd,
                target,
            )

        target = os.path.abspath(
            os.path.expanduser(target)
        )

        if not os.path.isdir(target):
            print(f"cd: directory not found: {target}")
            return

        # IMPORTANT:
        # Do not call os.chdir().
        #
        # Each Convexity session owns its own cwd.

        self.session.cwd = target

    # ========================================================
    # HISTORY
    # ========================================================

    def command_history(self, args: list[str]) -> None:

        try:
            history = self.session.get_history()

        except AttributeError:
            history = []

        if not history:
            print("No history.")
            return

        limit = None

        if args:
            try:
                limit = int(args[0])
            except ValueError:
                print("history: expected a number.")
                return

        if limit is not None:
            history = history[-limit:]

        for index, entry in enumerate(history, 1):

            if isinstance(entry, dict):
                command = entry.get(
                    "command",
                    "",
                )
            else:
                command = getattr(
                    entry,
                    "command",
                    str(entry),
                )

            print(f"{index:4}  {command}")

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    def command_env(self) -> None:

        environment = self.session.environment

        for key in sorted(environment):
            print(f"{key}={environment[key]}")

    # ========================================================
    # SET
    # ========================================================

    def command_set(self, args: list[str]) -> None:

        if len(args) < 2:
            print("Usage: set <name> <value>")
            return

        name = args[0]

        value = " ".join(args[1:])

        self.session.set_environment(
            name,
            value,
        )

    # ========================================================
    # UNSET
    # ========================================================

    def command_unset(self, args: list[str]) -> None:

        if len(args) != 1:
            print("Usage: unset <name>")
            return

        self.session.remove_environment(
            args[0]
        )

    # ========================================================
    # MAPLE
    # ========================================================

    def command_load_maple(self) -> None:

        try:
            if self.session.is_maple_loaded():
                print("Maple is already loaded.")
                return

            self.session.load_maple()

            print("Maple loaded.")
            print(
                "Maple will remain active until "
                "'kill maple' is used."
            )

        except Exception as exc:
            print(f"Maple: unable to load: {exc}")

    def command_kill_maple(self) -> None:

        try:
            if not self.session.is_maple_loaded():
                print("Maple is not loaded.")
                return

            self.session.kill_maple()

            print("Maple unloaded.")

        except Exception as exc:
            print(f"Maple: unable to unload: {exc}")

    # ========================================================
    # SYSTEM INFORMATION
    # ========================================================

    def command_sysinfo(self) -> None:

        print(f"System:      {platform.system()}")
        print(f"Release:     {platform.release()}")
        print(f"Version:     {platform.version()}")
        print(f"Machine:     {platform.machine()}")
        print(f"Processor:   {platform.processor()}")
        print(f"Python:      {platform.python_version()}")
        print(f"Directory:   {self.session.cwd}")

        try:
            print(
                f"Maple:       "
                f"{'loaded' if self.session.is_maple_loaded() else 'inactive'}"
            )
        except Exception:
            pass

    # ========================================================
    # PROCESSES
    # ========================================================

    def command_processes(self) -> None:

        try:
            processes = self.runtime.executor.list_processes()

        except AttributeError:
            print("Process information unavailable.")
            return

        if not processes:
            print("No active processes.")
            return

        print(
            f"{'PID':>8}  "
            f"{'STATE':<12}  "
            f"COMMAND"
        )

        print("-" * 60)

        for process in processes:

            pid = getattr(
                process,
                "pid",
                "?",
            )

            state = getattr(
                process,
                "state",
                "unknown",
            )

            command = getattr(
                process,
                "command",
                "",
            )

            print(
                f"{str(pid):>8}  "
                f"{str(state):<12}  "
                f"{command}"
            )

    # ========================================================
    # EXTERNAL COMMAND
    # ========================================================

    def command_external(self, command: str) -> None:
        """
        Execute an external command through Runtime.

        Runtime is the only execution path.
        """

        source = "human"

        # ----------------------------------------------------
        # Maple is not itself executed here.
        #
        # If a future Maple agent requests execution, it should
        # call Runtime with source="maple" and confirmed=True
        # after approval.
        # ----------------------------------------------------

        result = self.runtime.execute(
            self.session_id,
            command,
            source=source,
            confirmed=False,
        )

        if result.stdout:
            print(
                result.stdout,
                end=""
                if result.stdout.endswith("\n")
                else "\n",
            )

        if result.stderr:
            print(
                result.stderr,
                file=sys.stderr,
                end=""
                if result.stderr.endswith("\n")
                else "\n",
            )

    # ========================================================
    # BACKGROUND COMMAND
    # ========================================================

    def execute_background(
        self,
        command: str,
    ):
        """
        Start a background command through Runtime.
        """

        return self.runtime.execute_background(
            self.session_id,
            command,
            source="human",
            confirmed=False,
        )


# ============================================================
# CONVENIENCE ENTRY POINT
# ============================================================

def create_terminal() -> ConvexityTerminal:
    """
    Create a Convexity terminal instance.
    """

    return ConvexityTerminal()


def main() -> None:
    """
    Main executable entry point.
    """

    terminal = create_terminal()

    try:
        terminal.run()

    finally:
        # Do not forcibly close the global runtime here.
        # Other Convexity components may still be using it.
        pass


if __name__ == "__main__":
    main()
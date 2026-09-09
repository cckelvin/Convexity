"""
Convexity Interactive Terminal.

The main interface for users and AI agents (Maple) to interact with the system.
Routes commands to the appropriate handler (Filesystem or Executor).
"""

import sys
import os
import readline  # For command history on Linux/Mac. Windows alternative handled below.
from typing import Optional

from .config import config
from .filesystem import (
    get_current_directory,
    list_directory,
    change_directory,
    make_directory,
    touch_file,
    read_file,
    write_file,
    delete_path,
    FileSystemError
)
from .executor import execute_command, ExecutionResult
from .security import SecurityError


# Windows compatibility for readline
if sys.platform.startswith('win'):
    try:
        import pyreadline  # Optional dependency for better Windows support
    except ImportError:
        pass


class ConvexityTerminal:
    """Main Terminal Class."""

    def __init__(self):
        self.running = True
        self.history_file = os.path.expanduser("~/.convexity_history")
        
        # Load history
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass

    def start(self):
        """Starts the interactive terminal loop."""
        print(f"Welcome to {config.APP_NAME} v{config.VERSION}")
        print("Type 'help' for available commands.")
        print("-" * 40)

        while self.running:
            try:
                user_input = input(f"{get_current_directory()} > ")
            except EOFError:
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                print("\nInterrupted. Type 'exit' to quit.")
                continue

            if not user_input.strip():
                continue

            # Save to history
            readline.add_history(user_input)
            try:
                readline.write_history_file(self.history_file)
            except Exception:
                pass

            self.process_command(user_input.strip())

    def process_command(self, command_str: str):
        """Parses and executes a single command."""
        parts = command_str.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd == 'exit' or cmd == 'quit':
                self.running = False
                print("Goodbye!")
            
            elif cmd == 'help':
                self.show_help()
            
            elif cmd == 'clear':
                os.system('cls' if os.name == 'nt' else 'clear')
            
            elif cmd == 'version':
                print(f"{config.APP_NAME} version {config.VERSION}")
            
            # Filesystem Commands
            elif cmd == 'pwd':
                print(get_current_directory())
            
            elif cmd == 'ls':
                path = args[0] if args else None
                try:
                    items = list_directory(path)
                    if items:
                        print("  ".join(items))
                    else:
                        print("(empty directory)")
                except FileSystemError as e:
                    print(f"Error: {e}")
            
            elif cmd == 'cd':
                if not args:
                    print("Usage: cd <path>")
                    return
                try:
                    new_path = change_directory(args[0])
                    # Note: Prompt updates automatically in next iteration via get_current_directory()
                except FileSystemError as e:
                    print(f"Error: {e}")
            
            elif cmd == 'mkdir':
                if not args:
                    print("Usage: mkdir <path>")
                    return
                try:
                    path = make_directory(args[0], parents=True)
                    print(f"Created directory: {path}")
                except FileSystemError as e:
                    print(f"Error: {e}")
            
            elif cmd == 'touch':
                if not args:
                    print("Usage: touch <filename>")
                    return
                try:
                    path = touch_file(args[0])
                    print(f"Touched: {path}")
                except FileSystemError as e:
                    print(f"Error: {e}")
            
            elif cmd == 'cat':
                if not args:
                    print("Usage: cat <filename>")
                    return
                try:
                    content = read_file(args[0])
                    print(content)
                except FileSystemError as e:
                    print(f"Error: {e}")
            
            elif cmd == 'write':
                if len(args) < 2:
                    print("Usage: write <filename> <content>")
                    return
                filename = args[0]
                content = " ".join(args[1:])
                try:
                    path = write_file(filename, content)
                    print(f"Wrote to: {path}")
                except FileSystemError as e:
                    print(f"Error: {e}")

            elif cmd == 'rm':
                if not args:
                    print("Usage: rm <path>")
                    return
                # Simple confirmation for safety
                confirm = input(f"Are you sure you want to delete '{args[0]}'? (y/N): ")
                if confirm.lower() == 'y':
                    try:
                        msg = delete_path(args[0])
                        print(msg)
                    except FileSystemError as e:
                        print(f"Error: {e}")
                else:
                    print("Deletion cancelled.")

            # External Command Execution
            else:
                # Pass to executor
                result = execute_command(command_str)
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(f"Error: {result.stderr}", file=sys.stderr)
                
        except SecurityError as e:
            print(f"Security Violation: {e}")
        except Exception as e:
            print(f"Unexpected Error: {e}")

    def show_help(self):
        """Displays available commands."""
        help_text = """
Available Commands:
  help          Show this help message
  clear         Clear the terminal screen
  pwd           Print working directory
  ls [path]     List directory contents
  cd <path>     Change directory
  mkdir <path>  Create a directory
  touch <file>  Create an empty file
  cat <file>    Display file contents
  write <file> <content> Write content to a file
  rm <path>     Delete a file or empty directory
  version       Show Convexity version
  exit / quit   Exit the terminal

External Commands:
  Any allowlisted command (e.g., python, git) will be executed securely.
        """
        print(help_text)


def main():
    """Entry point for the terminal."""
    terminal = ConvexityTerminal()
    terminal.start()


if __name__ == "__main__":
    main()
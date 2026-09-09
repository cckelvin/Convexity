import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext

# ---------------------------------------------------------------------------
# Find Convexity project root
# ---------------------------------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Convexity
# ---------------------------------------------------------------------------

try:
    from terminal.runtime import TerminalRuntime
except Exception as e:
    raise RuntimeError(
        "Could not load Convexity TerminalRuntime.\n\n"
        f"Project root: {PROJECT_ROOT}\n\n"
        f"Error: {e}"
    )


# ---------------------------------------------------------------------------
# Windows Application
# ---------------------------------------------------------------------------

class ConvexityApp:

    def __init__(self, root):
        self.root = root

        self.root.title("Convexity")
        self.root.geometry("1000x650")
        self.root.minsize(700, 450)

        self.runtime = TerminalRuntime()
        self.session = self.runtime.create_session()

        self.build_ui()

        self.print_line("Convexity Terminal")
        self.print_line("Windows runtime initialized.")
        self.print_line("Type 'help' to see available commands.")
        self.print_line("")

        self.update_prompt()

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def build_ui(self):

        self.root.configure(bg="#0d1117")

        # Header
        header = tk.Frame(
            self.root,
            bg="#161b22",
            height=48
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="CONVEXITY",
            bg="#161b22",
            fg="white",
            font=("Segoe UI", 14, "bold")
        )
        title.pack(side="left", padx=16)

        status = tk.Label(
            header,
            text="● Terminal Online",
            bg="#161b22",
            fg="#7ee787",
            font=("Segoe UI", 10)
        )
        status.pack(side="right", padx=16)

        # Terminal output
        self.output = scrolledtext.ScrolledText(
            self.root,
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="white",
            selectbackground="#30363d",
            font=("Consolas", 11),
            wrap="word",
            borderwidth=0,
            highlightthickness=0
        )

        self.output.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(10, 5)
        )

        self.output.configure(state="disabled")

        # Input area
        bottom = tk.Frame(
            self.root,
            bg="#161b22",
            height=55
        )
        bottom.pack(fill="x")
        bottom.pack_propagate(False)

        self.prompt_label = tk.Label(
            bottom,
            text="convexity>",
            bg="#161b22",
            fg="#58a6ff",
            font=("Consolas", 11, "bold")
        )
        self.prompt_label.pack(
            side="left",
            padx=(12, 5)
        )

        self.command_entry = tk.Entry(
            bottom,
            bg="#0d1117",
            fg="white",
            insertbackground="white",
            font=("Consolas", 11),
            relief="flat"
        )

        self.command_entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
            pady=10
        )

        self.command_entry.bind(
            "<Return>",
            self.execute_command
        )

        self.command_entry.bind(
            "<Up>",
            self.history_up
        )

        self.command_entry.bind(
            "<Down>",
            self.history_down
        )

        run_button = tk.Button(
            bottom,
            text="Run",
            command=self.execute_command,
            bg="#238636",
            fg="white",
            activebackground="#2ea043",
            activeforeground="white",
            relief="flat",
            padx=18,
            font=("Segoe UI", 10, "bold")
        )

        run_button.pack(
            side="right",
            padx=(5, 12),
            pady=10
        )

        self.history = []
        self.history_index = 0

        self.command_entry.focus_set()

    # -----------------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------------

    def print_line(self, text=""):

        self.output.configure(state="normal")

        self.output.insert(
            "end",
            str(text) + "\n"
        )

        self.output.see("end")

        self.output.configure(state="disabled")

    # -----------------------------------------------------------------------
    # Prompt
    # -----------------------------------------------------------------------

    def update_prompt(self):

        try:
            cwd = self.session.cwd
        except Exception:
            cwd = os.getcwd()

        maple = ""

        try:
            if self.session.is_maple_loaded():
                maple = " [Maple]"
        except Exception:
            pass

        self.prompt_label.config(
            text=f"convexity:{cwd}{maple}>"
        )

    # -----------------------------------------------------------------------
    # Execute
    # -----------------------------------------------------------------------

    def execute_command(self, event=None):

        command = self.command_entry.get().strip()

        if not command:
            return "break"

        self.command_entry.delete(
            0,
            "end"
        )

        self.history.append(command)
        self.history_index = len(self.history)

        self.print_line(
            f"convexity:{self.session.cwd}> {command}"
        )

        # Exit
        if command.lower() in ("exit", "quit"):

            self.print_line("Closing Convexity...")

            self.root.after(
                100,
                self.close
            )

            return "break"

        try:

            result = self.runtime.execute(
                self.session.session_id,
                command,
                source="human"
            )

            if result.stdout:
                self.print_line(
                    result.stdout.rstrip()
                )

            if result.stderr:
                self.print_line(
                    result.stderr.rstrip()
                )

            if (
                not result.stdout
                and not result.stderr
                and result.return_code is not None
            ):
                self.print_line(
                    f"[exit code: {result.return_code}]"
                )

        except Exception as e:

            self.print_line(
                f"Convexity error: {e}"
            )

        self.print_line("")
        self.update_prompt()

        return "break"

    # -----------------------------------------------------------------------
    # History
    # -----------------------------------------------------------------------

    def history_up(self, event=None):

        if not self.history:
            return "break"

        self.history_index = max(
            0,
            self.history_index - 1
        )

        self.command_entry.delete(
            0,
            "end"
        )

        self.command_entry.insert(
            0,
            self.history[self.history_index]
        )

        return "break"

    def history_down(self, event=None):

        if not self.history:
            return "break"

        self.history_index = min(
            len(self.history),
            self.history_index + 1
        )

        self.command_entry.delete(
            0,
            "end"
        )

        if self.history_index < len(self.history):

            self.command_entry.insert(
                0,
                self.history[self.history_index]
            )

        return "break"

    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------

    def close(self):

        try:
            self.runtime.close()
        except Exception:
            pass

        self.root.destroy()


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def main():

    root = tk.Tk()

    app = ConvexityApp(root)

    root.protocol(
        "WM_DELETE_WINDOW",
        app.close
    )

    root.mainloop()


if __name__ == "__main__":
    main()

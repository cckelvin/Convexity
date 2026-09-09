"""
Convexity Terminal
Version 0.1
"""

from executor import execute


def start_terminal():
    print("================================")
    print("        CONVEXITY TERMINAL")
    print("             v0.1")
    print("================================")
    print("Type 'help' for commands.")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            command = input("convexity> ").strip()

            if not command:
                continue

            if command.lower() in ("exit", "quit"):
                print("Closing Convexity.")
                break

            if command.lower() == "help":
                show_help()
                continue

            result = execute(command)

            if result:
                print(result)

        except KeyboardInterrupt:
            print("\nUse 'exit' to close Convexity.")

        except EOFError:
            break

        except Exception as error:
            print(f"Terminal error: {error}")


def show_help():
    print("""
Available commands:

  help       Show this help
  exit       Close Convexity
  quit       Close Convexity

More commands will be added through the
Convexity executor, tools, and Maple.
""")


if __name__ == "__main__":
    start_terminal()

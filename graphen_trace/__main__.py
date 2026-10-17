"""Graphen Trace command-line entry point."""

from graphen_trace.application import Application


def main() -> int:
    """Runs the command-line application."""
    return Application().run()


if __name__ == "__main__":
    main()

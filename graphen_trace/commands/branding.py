"""Shared CLI branding."""

from pyfiglet import Figlet


def render_banner() -> str:
    """Renders the Graphen Trace command-line banner."""
    return Figlet(font="slant").renderText("Graphen Trace")

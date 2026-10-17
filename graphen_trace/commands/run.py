"""Commands that launch an integrated agent service."""

import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

from cleo.commands.command import Command
from cleo.helpers import argument

from graphen_trace.config.settings import settings
from graphen_trace.services.server import serve


class RunOpenCodeCommand(Command):
    """Starts the proxy service and launches OpenCode as its child process."""

    name = "run opencode"
    description = "Launches OpenCode through the temporary local proxy"
    arguments = [
        argument("args", "Arguments passed to OpenCode", optional=True, multiple=True)
    ]

    def handle(self) -> int:
        executable = shutil.which("opencode")
        if executable is None:
            self.line_error("OpenCode was not found on PATH.")
            return 1

        server = threading.Thread(
            target=serve,
            kwargs={"proxy_enabled": True},
            daemon=True,
        )
        server.start()
        if not _wait_for_server():
            self.line_error("The local Graphen Trace service did not start.")
            return 1

        environment = os.environ.copy()
        environment["OPENAI_BASE_URL"] = f"http://{settings.host}:{settings.port}/v1"
        return subprocess.call([executable, *self.argument("args")], env=environment)


def _wait_for_server() -> bool:
    """Waits briefly for the local HTTP service to accept requests."""
    for _ in range(50):
        try:
            with urllib.request.urlopen(
                f"http://{settings.host}:{settings.port}/api/health", timeout=0.2
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    return False

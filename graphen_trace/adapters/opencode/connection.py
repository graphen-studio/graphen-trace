"""Read-only discovery of the existing OpenCode shared service connection."""

import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from graphen_trace.config.settings import Settings


@dataclass(frozen=True)
class Connection:
    """Local connection details; authentication is never serialized or logged."""

    url: str
    instance_id: str
    password: str | None = field(default=None, repr=False)


def discover_connection(settings: Settings) -> Connection:
    """Reads service registration without starting, stopping or reconfiguring it."""
    if settings.opencode_url:
        url = settings.opencode_url
        instance_id = url
        password = settings.opencode_password
    else:
        try:
            registration = json.loads(settings.opencode_service_file.read_text())
        except FileNotFoundError as error:
            raise ValueError("OpenCode shared service is not registered") from error

        if not isinstance(registration, dict):
            raise ValueError("Invalid OpenCode service registration")

        url = registration.get("url")
        instance_id = registration.get("id")
        password = settings.opencode_password or registration.get("password")

    if not isinstance(url, str) or not isinstance(instance_id, str):
        raise ValueError("Invalid OpenCode service connection")

    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "OpenCode events require a loopback service URL without credentials"
        )

    if password is not None and not isinstance(password, str):
        raise ValueError("Invalid OpenCode service authentication")

    return Connection(url.rstrip("/"), instance_id, password)

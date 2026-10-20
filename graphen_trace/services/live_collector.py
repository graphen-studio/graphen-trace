"""Lifecycle of the optional live OpenCode event subscription."""

import asyncio
import logging
import sqlite3

import httpx

from graphen_trace.adapters.opencode.connection import discover_connection
from graphen_trace.adapters.opencode.events import check_response, read_frames
from graphen_trace.config.settings import Settings
from graphen_trace.services.storage import Storage

LOGGER = logging.getLogger(__name__)
AGENT = "opencode"
SOURCE = "opencode:sse:v2"


class LiveCollector:
    """Persists observed SSE events independently of SQLite message projections."""

    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.status = {
            "state": "starting",
            "last_seen": None,
            "detail": "Only events from the connected service instance are observed",
            "possible_gap": True,
        }

    async def subscribe(self) -> None:
        """Connects to the existing V2 server and persists each complete envelope."""

        connection = await asyncio.to_thread(discover_connection, self.settings)
        auth = (
            httpx.BasicAuth("opencode", connection.password)
            if connection.password
            else None
        )
        async with httpx.AsyncClient(
            auth=auth,
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            try:
                warnings = check_response(
                    await client.get(f"{connection.url}/api/info")
                )
            except (ValueError, httpx.HTTPError):
                warnings = ["Server identity unavailable; checking SSE independently"]

            async with client.stream(
                "GET",
                f"{connection.url}/api/event",
                headers={"accept": "text/event-stream"},
            ) as response:

                if response.status_code != 200:
                    raise ValueError(
                        f"OpenCode SSE returned HTTP {response.status_code}"
                    )

                content_type = response.headers.get("content-type", "").lower()
                if "text/event-stream" not in content_type:
                    raise ValueError("OpenCode API did not return an SSE stream")

                self.status.update(
                    state="partial" if warnings else "connected",
                    detail="Live events from one instance; no replay guarantee",
                    warnings=warnings,
                )

                await asyncio.to_thread(
                    self.storage.mark_live, "connected", SOURCE, AGENT
                )
                async for event in read_frames(response.aiter_lines()):
                    await asyncio.to_thread(
                        self.storage.save_event,
                        connection.instance_id,
                        event,
                        SOURCE,
                        AGENT,
                    )
                    self.status["last_seen"] = event["observed_at"]

                    if event["normalization_warnings"]:
                        warnings = sorted(
                            set(warnings + event["normalization_warnings"])
                        )
                        self.status.update(state="partial", warnings=warnings)

        raise ValueError("OpenCode SSE disconnected; live events may be missing")

    async def run(self) -> None:
        """Retries unavailable subscriptions without interrupting passive polling."""

        try:
            while True:
                try:
                    await self.subscribe()
                except (
                    OSError,
                    ValueError,
                    httpx.HTTPError,
                    httpx.InvalidURL,
                    sqlite3.Error,
                ) as error:
                    reason = (
                        str(error)
                        if isinstance(error, ValueError)
                        else "Local stream unavailable"
                    )
                    detail = f"{reason}; SQLite polling continues; possible event gap"
                    if self.status["state"] != "unavailable":
                        LOGGER.warning(detail)
                        await self._mark("disconnected")
                    self.status.update(
                        state="unavailable", detail=detail, possible_gap=True
                    )
                await asyncio.sleep(3)
        finally:
            await self._mark("stopped")

    async def _mark(self, state: str) -> None:
        """Records connection boundaries without hiding storage failures."""

        try:
            await asyncio.to_thread(self.storage.mark_live, state, SOURCE, AGENT)
        except sqlite3.Error:
            LOGGER.warning("Could not persist live collection state")

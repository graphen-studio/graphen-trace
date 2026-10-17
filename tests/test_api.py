"""Tests for initial dashboard API routes."""

import unittest

from fastapi.testclient import TestClient

from graphen_trace.api.app import create_app


class ApiRoutesTestCase(unittest.TestCase):
    """Verifies health, frontend, and optional proxy route behavior."""

    def test_health_and_frontend_are_served(self) -> None:
        """Health and SPA fallback routes return successful responses."""
        client = TestClient(create_app())

        self.assertEqual(client.get("/api/health").json()["status"], "ok")
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/api/not-implemented").status_code, 404)

    def test_proxy_route_is_only_enabled_explicitly(self) -> None:
        """The proxy feature remains disabled unless explicitly requested."""
        passive_app = create_app()
        proxy_app = create_app(proxy_enabled=True)

        self.assertFalse(passive_app.state.proxy_enabled)
        self.assertTrue(proxy_app.state.proxy_enabled)


if __name__ == "__main__":
    unittest.main()

"""Contracts for the private operational dashboard."""

import unittest
from pathlib import Path

from api.admin import handle_get, has_admin_access, validate_message_status


class AdminAccessTests(unittest.TestCase):
    def test_accepts_only_the_configured_bearer_token(self) -> None:
        self.assertTrue(has_admin_access("Bearer token-seguro", "token-seguro"))
        self.assertFalse(has_admin_access("Bearer token-incorrecto", "token-seguro"))
        self.assertFalse(has_admin_access("", "token-seguro"))
        self.assertFalse(has_admin_access("Bearer token-seguro", ""))

    def test_only_allows_known_message_statuses(self) -> None:
        self.assertEqual(validate_message_status("respondido"), "respondido")
        with self.assertRaisesRegex(ValueError, "estado"):
            validate_message_status("borrado")

    def test_dashboard_explains_how_to_run_it_when_opened_as_a_file(self) -> None:
        dashboard = Path("admin.html").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8000/admin.html", dashboard)

    def test_local_server_adapter_returns_unauthorized_instead_of_crashing(self) -> None:
        class FakeRequest:
            headers = {}
            path = "/api/admin?resource=messages"
            response = None

            def _send_json(self, status, payload) -> None:
                self.response = (status, payload)

        request = FakeRequest()
        handle_get(request)

        self.assertEqual(request.response[0], 401)


if __name__ == "__main__":
    unittest.main()

"""Contracts for the Supabase-backed appointment repository."""

import json
import unittest
from unittest.mock import patch

from climastock.booking import AppointmentConflictError, BookingRequest
from climastock.repository_factory import repository_from_environment
from climastock.supabase_repository import SupabaseAppointmentRepository


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class SupabaseAppointmentRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests = []
        self.responses = []
        self.repository = SupabaseAppointmentRepository(
            "https://example.supabase.co", "sb_secret_test", self._open,
        )

    def _open(self, request, timeout: float):
        self.requests.append((request, timeout))
        return self.responses.pop(0)

    def test_creates_an_appointment_through_the_rest_api(self) -> None:
        self.responses.append(FakeResponse(201, [{
            "id": "a1", "patient_name": "Ana Gomez", "contact": "300 000 0000",
            "service": "Consulta general", "professional": "Dra. Ruiz",
            "starts_at": "2026-10-06T09:00:00", "ends_at": "2026-10-06T09:30:00",
            "status": "confirmada",
        }]))

        appointment = self.repository.create(BookingRequest(
            patient_name="Ana Gomez", contact="300 000 0000", service="Consulta general",
            professional="Dra. Ruiz", starts_at="2026-10-06T09:00", duration_minutes=30,
        ))

        request, timeout = self.requests[0]
        self.assertEqual(request.full_url, "https://example.supabase.co/rest/v1/appointments")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Apikey"], "sb_secret_test")
        self.assertEqual(request.headers["Authorization"], "Bearer sb_secret_test")
        self.assertEqual(timeout, 10)
        self.assertEqual(json.loads(request.data), {
            "patient_name": "Ana Gomez", "contact": "300 000 0000",
            "service": "Consulta general", "professional": "Dra. Ruiz",
            "starts_at": "2026-10-06T09:00", "ends_at": "2026-10-06T09:30",
            "status": "confirmada",
        })
        self.assertEqual(appointment.ends_at, "2026-10-06T09:30")

    def test_translates_a_database_conflict_without_leaking_database_details(self) -> None:
        self.responses.append(FakeResponse(409, {
            "message": "conflicting key value violates exclusion constraint",
        }))

        with self.assertRaisesRegex(AppointmentConflictError, "profesional ya tiene"):
            self.repository.create(BookingRequest(
                patient_name="Ana Gomez", contact="300", service="Consulta general",
                professional="Dra. Ruiz", starts_at="2026-10-06T09:00", duration_minutes=30,
            ))

    def test_lists_only_the_requested_day_in_chronological_order(self) -> None:
        self.responses.append(FakeResponse(200, []))

        self.assertEqual(self.repository.list_for_date("2026-10-06"), [])

        request, _ = self.requests[0]
        self.assertIn("starts_at=gte.2026-10-06T00%3A00", request.full_url)
        self.assertIn("starts_at=lt.2026-10-07T00%3A00", request.full_url)
        self.assertIn("order=starts_at.asc", request.full_url)


class RepositoryConfigurationTests(unittest.TestCase):
    def test_uses_supabase_only_when_both_required_environment_variables_exist(self) -> None:
        with patch.dict("os.environ", {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "sb_secret_test",
        }, clear=True):
            repository = repository_from_environment()

        self.assertIsInstance(repository, SupabaseAppointmentRepository)

    def test_rejects_partial_supabase_configuration(self) -> None:
        with patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SUPABASE_SECRET_KEY"):
                repository_from_environment()


if __name__ == "__main__":
    unittest.main()

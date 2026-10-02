"""Booking rules and API contract for the ClinicaFlow appointments portal."""

import unittest
from pathlib import Path
from uuid import uuid4

from api.appointments import create_appointment_payload, list_appointments_payload
from climastock.booking import AppointmentConflictError, AppointmentRepository, BookingRequest


def _request(**overrides: object) -> BookingRequest:
    values: dict[str, object] = {
        "patient_name": "Ana Gomez", "contact": "300 000 0000",
        "service": "Medicina general", "professional": "Dra. Ruiz",
        "starts_at": "2026-10-06T09:00", "duration_minutes": 30,
    }
    values.update(overrides)
    return BookingRequest(**values)  # type: ignore[arg-type]


class AppointmentRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_path = Path(".test-output") / f"booking-{uuid4()}.db"
        self.repository = AppointmentRepository(self.database_path)

    def tearDown(self) -> None:
        self.database_path.unlink(missing_ok=True)

    def test_books_an_available_slot_and_returns_a_confirmed_appointment(self) -> None:
        appointment = self.repository.create(_request())
        self.assertEqual(appointment.status, "confirmada")
        self.assertEqual(appointment.patient_name, "Ana Gomez")
        self.assertEqual(appointment.ends_at, "2026-10-06T09:30")
        self.assertTrue(appointment.id)

    def test_rejects_an_overlapping_appointment_for_the_same_professional(self) -> None:
        self.repository.create(_request())
        with self.assertRaises(AppointmentConflictError):
            self.repository.create(_request(patient_name="Luis Perez", starts_at="2026-10-06T09:15"))

    def test_cancelled_slots_free_capacity(self) -> None:
        first = self.repository.create(_request())
        self.repository.cancel(first.id)
        appointment = self.repository.create(_request(patient_name="Luis Perez"))
        self.assertEqual(appointment.starts_at, "2026-10-06T09:00")

    def test_reschedules_an_appointment_when_the_new_slot_is_free(self) -> None:
        appointment = self.repository.create(_request())
        moved = self.repository.reschedule(appointment.id, "2026-10-06T10:00")
        self.assertEqual(moved.starts_at, "2026-10-06T10:00")
        self.assertEqual(moved.ends_at, "2026-10-06T10:30")

    def test_rejects_incomplete_or_invalid_booking_data(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.create(_request(patient_name="", duration_minutes=0))


class AppointmentApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_path = Path(".test-output") / f"booking-{uuid4()}.db"
        self.repository = AppointmentRepository(self.database_path)

    def tearDown(self) -> None:
        self.database_path.unlink(missing_ok=True)

    def test_create_payload_confirms_booking_with_operational_fields(self) -> None:
        payload = create_appointment_payload({
            "patient_name": "Ana Gomez", "contact": "300 000 0000", "service": "Medicina general",
            "professional": "Dra. Ruiz", "starts_at": "2026-10-06T09:00", "duration_minutes": 30,
        }, self.repository)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["status"], "confirmada")
        self.assertEqual(payload["data"]["ends_at"], "2026-10-06T09:30")

    def test_list_payload_returns_bookings_in_chronological_order(self) -> None:
        self.repository.create(_request(starts_at="2026-10-06T10:00"))
        self.repository.create(_request(patient_name="Luis Perez", starts_at="2026-10-06T09:00"))
        payload = list_appointments_payload("2026-10-06", self.repository)
        self.assertEqual([item["patient_name"] for item in payload["data"]], ["Luis Perez", "Ana Gomez"])


if __name__ == "__main__":
    unittest.main()

"""JSON payload helpers for the local ClinicaFlow appointment portal."""

from __future__ import annotations

from dataclasses import asdict

from climastock.booking import AppointmentStore, BookingRequest


def create_appointment_payload(data: dict, repository: AppointmentStore) -> dict:
    request = BookingRequest(
        patient_name=str(data.get("patient_name", "")), contact=str(data.get("contact", "")),
        service=str(data.get("service", "")), professional=str(data.get("professional", "")),
        starts_at=str(data.get("starts_at", "")), duration_minutes=int(data.get("duration_minutes", 30)),
    )
    return {"success": True, "data": asdict(repository.create(request))}


def list_appointments_payload(date: str, repository: AppointmentStore) -> dict:
    return {"success": True, "data": [asdict(item) for item in repository.list_for_date(date)]}


def cancel_appointment_payload(appointment_id: str, repository: AppointmentStore) -> dict:
    return {"success": True, "data": asdict(repository.cancel(appointment_id))}


def reschedule_appointment_payload(appointment_id: str, starts_at: str, repository: AppointmentStore) -> dict:
    return {"success": True, "data": asdict(repository.reschedule(appointment_id, starts_at))}

"""Small, local appointment-booking domain for ClinicaFlow.

The module deliberately stores only the information needed to reserve and
manage a visit. It is not a clinical record and does not make care decisions.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class AppointmentConflictError(ValueError):
    """Raised when a professional already has an active appointment."""


@dataclass(frozen=True)
class BookingRequest:
    patient_name: str
    contact: str
    service: str
    professional: str
    starts_at: str
    duration_minutes: int = 30


@dataclass(frozen=True)
class Appointment:
    id: str
    patient_name: str
    contact: str
    service: str
    professional: str
    starts_at: str
    ends_at: str
    status: str


class AppointmentStore(Protocol):
    def create(self, request: BookingRequest) -> Appointment: ...

    def list_for_date(self, date: str) -> list[Appointment]: ...

    def cancel(self, appointment_id: str) -> Appointment: ...

    def reschedule(self, appointment_id: str, starts_at: str) -> Appointment: ...


class AppointmentRepository:
    """SQLite repository with conflict checks for a single local clinic."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self._database_path = str(database_path or Path(__file__).resolve().parent.parent / "appointments.db")
        self._initialize()

    def create(self, request: BookingRequest) -> Appointment:
        normalized = _normalize_request(request)
        starts_at = _parse_timestamp(normalized.starts_at)
        ends_at = starts_at.timestamp() + normalized.duration_minutes * 60
        ends_text = datetime.fromtimestamp(ends_at).isoformat(timespec="minutes")
        appointment = Appointment(
            id=str(uuid4()), patient_name=normalized.patient_name, contact=normalized.contact,
            service=normalized.service, professional=normalized.professional,
            starts_at=starts_at.isoformat(timespec="minutes"), ends_at=ends_text, status="confirmada",
        )
        with self._connection() as connection:
            overlap = connection.execute(
                """SELECT 1 FROM appointments
                   WHERE professional = ? AND status = 'confirmada'
                   AND starts_at < ? AND ends_at > ? LIMIT 1""",
                (appointment.professional, appointment.ends_at, appointment.starts_at),
            ).fetchone()
            if overlap:
                raise AppointmentConflictError("Ese profesional ya tiene una cita en ese horario.")
            connection.execute(
                """INSERT INTO appointments
                (id, patient_name, contact, service, professional, starts_at, ends_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (appointment.id, appointment.patient_name, appointment.contact, appointment.service,
                 appointment.professional, appointment.starts_at, appointment.ends_at, appointment.status),
            )
        return appointment

    def list_for_date(self, date: str) -> list[Appointment]:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("La fecha debe tener el formato AAAA-MM-DD.") from error
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, patient_name, contact, service, professional, starts_at, ends_at, status
                   FROM appointments WHERE substr(starts_at, 1, 10) = ?
                   ORDER BY starts_at ASC""", (date,),
            ).fetchall()
        return [Appointment(*row) for row in rows]

    def cancel(self, appointment_id: str) -> Appointment:
        if not appointment_id.strip():
            raise ValueError("La cita es obligatoria.")
        with self._connection() as connection:
            row = connection.execute(
                """SELECT id, patient_name, contact, service, professional, starts_at, ends_at, status
                   FROM appointments WHERE id = ?""", (appointment_id,),
            ).fetchone()
            if row is None:
                raise ValueError("No encontramos esa cita.")
            connection.execute("UPDATE appointments SET status = 'cancelada' WHERE id = ?", (appointment_id,))
        return Appointment(*row[:-1], "cancelada")

    def reschedule(self, appointment_id: str, starts_at: str) -> Appointment:
        """Move a confirmed appointment when its professional is available."""
        new_start = _parse_timestamp(starts_at.strip())
        with self._connection() as connection:
            row = connection.execute(
                """SELECT id, patient_name, contact, service, professional, starts_at, ends_at, status
                   FROM appointments WHERE id = ?""", (appointment_id,)
            ).fetchone()
            if row is None or row[-1] != "confirmada":
                raise ValueError("No encontramos una cita confirmada para reprogramar.")
            old_start = _parse_timestamp(row[5])
            duration_seconds = (_parse_timestamp(row[6]) - old_start).total_seconds()
            new_end = datetime.fromtimestamp(new_start.timestamp() + duration_seconds).isoformat(timespec="minutes")
            new_start_text = new_start.isoformat(timespec="minutes")
            overlap = connection.execute(
                """SELECT 1 FROM appointments WHERE professional = ? AND status = 'confirmada'
                   AND id != ? AND starts_at < ? AND ends_at > ? LIMIT 1""",
                (row[4], appointment_id, new_end, new_start_text),
            ).fetchone()
            if overlap:
                raise AppointmentConflictError("Ese profesional ya tiene una cita en ese horario.")
            connection.execute("UPDATE appointments SET starts_at = ?, ends_at = ? WHERE id = ?", (new_start_text, new_end, appointment_id))
        return Appointment(*row[:5], new_start_text, new_end, "confirmada")

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY,
                    patient_name TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    service TEXT NOT NULL,
                    professional TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('confirmada', 'cancelada'))
                )"""
            )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self._database_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _normalize_request(request: BookingRequest) -> BookingRequest:
    values = {
        "patient_name": request.patient_name.strip(), "contact": request.contact.strip(),
        "service": request.service.strip(), "professional": request.professional.strip(),
        "starts_at": request.starts_at.strip(),
    }
    if not all(values.values()):
        raise ValueError("Completa todos los campos de la cita.")
    if len(values["patient_name"]) > 100 or len(values["contact"]) > 120:
        raise ValueError("Los datos de contacto son demasiado largos.")
    if request.duration_minutes not in (15, 30, 45, 60):
        raise ValueError("La duración debe ser de 15, 30, 45 o 60 minutos.")
    return BookingRequest(**values, duration_minutes=request.duration_minutes)


def _parse_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Selecciona una fecha y hora válidas.") from error
    if timestamp.second or timestamp.microsecond:
        raise ValueError("La hora debe registrarse por minutos.")
    return timestamp

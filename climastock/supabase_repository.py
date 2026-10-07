"""Supabase REST implementation for ClinicaFlow appointments."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from climastock.booking import (Appointment, AppointmentConflictError, BookingRequest,
                                _normalize_request, _parse_timestamp)

HttpOpener = Callable[[Request, float], object]


class SupabaseUnavailableError(RuntimeError):
    """Raised when Supabase cannot be reached or returns an unexpected error."""


class SupabaseAppointmentRepository:
    """Persist appointments through a server-side Supabase secret key."""

    def __init__(self, url: str, secret_key: str, opener: HttpOpener = urlopen) -> None:
        normalized_url = url.rstrip("/")
        if not normalized_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("SUPABASE_URL debe ser una URL HTTPS válida.")
        if not secret_key.strip():
            raise ValueError("SUPABASE_SECRET_KEY es obligatoria.")
        self._endpoint = f"{normalized_url}/rest/v1/appointments"
        self._secret_key = secret_key
        self._opener = opener

    def create(self, request: BookingRequest) -> Appointment:
        normalized = _normalize_request(request)
        starts_at = _parse_timestamp(normalized.starts_at)
        ends_at = starts_at + timedelta(minutes=normalized.duration_minutes)
        payload = {
            "patient_name": normalized.patient_name,
            "contact": normalized.contact,
            "service": normalized.service,
            "professional": normalized.professional,
            "starts_at": starts_at.isoformat(timespec="minutes"),
            "ends_at": ends_at.isoformat(timespec="minutes"),
            "status": "confirmada",
        }
        rows = self._request("POST", "", payload)
        return _appointment_from_row(_single_row(rows))

    def list_for_date(self, date: str) -> list[Appointment]:
        day_start = _parse_date(date)
        next_day = day_start + timedelta(days=1)
        query = urlencode({
            "select": "id,patient_name,contact,service,professional,starts_at,ends_at,status",
            "starts_at": f"gte.{day_start.isoformat(timespec='minutes')}",
            "starts_at": f"gte.{day_start.isoformat(timespec='minutes')}",
            "order": "starts_at.asc",
        })
        # urlencode cannot represent duplicate keys from a dict. Keep the bounded
        # date range explicit so PostgREST can use the starts_at index.
        query = urlencode([
            ("select", "id,patient_name,contact,service,professional,starts_at,ends_at,status"),
            ("starts_at", f"gte.{day_start.isoformat(timespec='minutes')}"),
            ("starts_at", f"lt.{next_day.isoformat(timespec='minutes')}"),
            ("order", "starts_at.asc"),
        ])
        rows = self._request("GET", f"?{query}")
        if not isinstance(rows, list):
            raise SupabaseUnavailableError("Respuesta inesperada del servicio de agenda.")
        return [_appointment_from_row(row) for row in rows]

    def cancel(self, appointment_id: str) -> Appointment:
        identifier = _appointment_id(appointment_id)
        rows = self._request("PATCH", f"?{urlencode({'id': f'eq.{identifier}'})}", {
            "status": "cancelada",
        })
        return _appointment_from_row(_single_row(rows, "No encontramos esa cita."))

    def reschedule(self, appointment_id: str, starts_at: str) -> Appointment:
        identifier = _appointment_id(appointment_id)
        current_rows = self._request("GET", f"?{urlencode({'id': f'eq.{identifier}'})}")
        current = _appointment_from_row(_single_row(
            current_rows, "No encontramos una cita confirmada para reprogramar.",
        ))
        if current.status != "confirmada":
            raise ValueError("No encontramos una cita confirmada para reprogramar.")
        new_start = _parse_timestamp(starts_at.strip())
        duration = _parse_timestamp(current.ends_at) - _parse_timestamp(current.starts_at)
        new_end = new_start + duration
        rows = self._request("PATCH", f"?{urlencode({'id': f'eq.{identifier}'})}", {
            "starts_at": new_start.isoformat(timespec="minutes"),
            "ends_at": new_end.isoformat(timespec="minutes"),
        })
        return _appointment_from_row(_single_row(rows))

    def _request(self, method: str, query: str, payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "apikey": self._secret_key,
            "Authorization": f"Bearer {self._secret_key}",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self._endpoint}{query}", data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=10) as response:
                status = response.status
                body = response.read()
        except HTTPError as error:
            status = error.code
            body = error.read()
        except (URLError, TimeoutError) as error:
            raise SupabaseUnavailableError("No fue posible conectar con el servicio de agenda.") from error

        if status == 409:
            raise AppointmentConflictError("Ese profesional ya tiene una cita en ese horario.")
        if not 200 <= status < 300:
            raise SupabaseUnavailableError("No fue posible completar la operación de agenda.")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SupabaseUnavailableError("Respuesta inesperada del servicio de agenda.") from error


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.") from error


def _appointment_id(value: str) -> str:
    try:
        return str(UUID(value.strip()))
    except (AttributeError, ValueError) as error:
        raise ValueError("La cita es obligatoria.") from error


def _single_row(value, message: str = "No fue posible guardar la cita.") -> dict:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError(message)
    return value[0]


def _appointment_from_row(row: dict) -> Appointment:
    try:
        return Appointment(
            id=str(row["id"]), patient_name=str(row["patient_name"]), contact=str(row["contact"]),
            service=str(row["service"]), professional=str(row["professional"]),
            starts_at=_as_minutes(row["starts_at"]), ends_at=_as_minutes(row["ends_at"]),
            status=str(row["status"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SupabaseUnavailableError("Respuesta inesperada del servicio de agenda.") from error


def _as_minutes(value: object) -> str:
    normalized = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).replace(tzinfo=None).isoformat(timespec="minutes")

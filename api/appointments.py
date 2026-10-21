"""Appointment API payload helpers and Vercel HTTP handler."""

from __future__ import annotations

import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import os
from urllib.parse import parse_qs, urlparse

from climastock.booking import AppointmentConflictError, AppointmentStore, BookingRequest
from climastock.supabase_repository import SupabaseAppointmentRepository, SupabaseUnavailableError


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


class handler(BaseHTTPRequestHandler):
    """Vercel handler for creating and managing clinic appointments."""

    def do_GET(self) -> None:
        try:
            date = parse_qs(urlparse(self.path).query).get("date", [""])[0]
            payload = list_appointments_payload(date, _repository_from_environment())
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
            return
        except (RuntimeError, SupabaseUnavailableError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "success": False, "error": "Servicio de agenda no disponible. Verifica la configuración de Supabase.",
            })
            return
        self._send_json(HTTPStatus.OK, payload)

    def do_POST(self) -> None:
        try:
            payload = create_appointment_payload(_read_json(self), _repository_from_environment())
        except AppointmentConflictError as error:
            self._send_json(HTTPStatus.CONFLICT, {"success": False, "error": str(error)})
            return
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
            return
        except (RuntimeError, SupabaseUnavailableError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "success": False, "error": "Servicio de agenda no disponible. Verifica la configuración de Supabase.",
            })
            return
        self._send_json(HTTPStatus.CREATED, payload)

    def do_DELETE(self) -> None:
        try:
            appointment_id = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            payload = cancel_appointment_payload(appointment_id, _repository_from_environment())
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
            return
        except (RuntimeError, SupabaseUnavailableError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "success": False, "error": "Servicio de agenda no disponible. Verifica la configuración de Supabase.",
            })
            return
        self._send_json(HTTPStatus.OK, payload)

    def do_PATCH(self) -> None:
        try:
            data = _read_json(self)
            payload = reschedule_appointment_payload(
                str(data.get("id", "")), str(data.get("starts_at", "")), _repository_from_environment(),
            )
        except AppointmentConflictError as error:
            self._send_json(HTTPStatus.CONFLICT, {"success": False, "error": str(error)})
            return
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
            return
        except (RuntimeError, SupabaseUnavailableError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "success": False, "error": "Servicio de agenda no disponible. Verifica la configuración de Supabase.",
            })
            return
        self._send_json(HTTPStatus.OK, payload)

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _repository_from_environment() -> SupabaseAppointmentRepository:
    url = os.getenv("SUPABASE_URL", "").strip()
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise RuntimeError("Falta la configuración de Supabase.")
    try:
        return SupabaseAppointmentRepository(url, secret_key)
    except ValueError as error:
        raise RuntimeError("La configuración de Supabase no es válida.") from error


def _read_json(request: BaseHTTPRequestHandler) -> dict:
    try:
        size = int(request.headers.get("Content-Length", "0"))
    except ValueError:
        size = 0
    if size <= 0 or size > 10_000:
        raise ValueError("La solicitud no es válida.")
    payload = json.loads(request.rfile.read(size).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("La solicitud no es válida.")
    return payload

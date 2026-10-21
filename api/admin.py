"""Authenticated operational dashboard API."""

from __future__ import annotations

import hmac
import json
import os
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from climastock.admin_repository import AdminRepositoryError, SupabaseAdminRepository

MESSAGE_STATUSES = frozenset({"nuevo", "respondido", "cita_creada"})


def has_admin_access(authorization: str, configured_token: str) -> bool:
    """Compare a supplied bearer token without leaking the configured token."""
    prefix = "Bearer "
    if not configured_token or not authorization.startswith(prefix):
        return False
    return hmac.compare_digest(authorization[len(prefix):], configured_token)


def validate_message_status(value: object) -> str:
    status = str(value).strip()
    if status not in MESSAGE_STATUSES:
        raise ValueError("El estado del mensaje no es válido.")
    return status


class handler(BaseHTTPRequestHandler):
    """Vercel handler for private clinic operations at /api/admin."""

    def do_GET(self) -> None:
        handle_get(self)

    def do_PATCH(self) -> None:
        handle_patch(self)

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


def handle_get(request) -> None:
    """Serve the admin GET API through Vercel or the local HTTP server."""
    if not _is_authorized(request):
        return
    query = parse_qs(urlparse(request.path).query)
    try:
        resource = query.get("resource", [""])[0]
        repository = _repository_from_environment()
        if resource == "messages":
            status = query.get("status", [""])[0]
            if status:
                validate_message_status(status)
            payload = repository.list_messages(status)
        elif resource == "appointments":
            selected_date = query.get("date", [date.today().isoformat()])[0]
            date.fromisoformat(selected_date)
            payload = repository.list_appointments(selected_date)
        else:
            raise ValueError("Recurso no válido.")
    except ValueError as error:
        request._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
        return
    except (RuntimeError, AdminRepositoryError):
        request._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"success": False, "error": "Servicio no disponible."})
        return
    request._send_json(HTTPStatus.OK, {"success": True, "data": payload})


def handle_patch(request) -> None:
    """Update a message state through Vercel or the local HTTP server."""
    if not _is_authorized(request):
        return
    try:
        payload = _read_json(request)
        message_id = str(payload.get("id", ""))
        status = validate_message_status(payload.get("status", ""))
        updated = _repository_from_environment().update_message_status(message_id, status)
    except ValueError as error:
        request._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})
        return
    except (RuntimeError, AdminRepositoryError):
        request._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"success": False, "error": "Servicio no disponible."})
        return
    request._send_json(HTTPStatus.OK, {"success": True, "data": updated})


def _is_authorized(request) -> bool:
    if has_admin_access(request.headers.get("Authorization", ""), os.getenv("ADMIN_DASHBOARD_TOKEN", "")):
        return True
    request._send_json(HTTPStatus.UNAUTHORIZED, {"success": False, "error": "No autorizado."})
    return False


def _read_json(request) -> dict:
    try:
        size = int(request.headers.get("Content-Length", "0"))
    except ValueError:
        size = 0
    if size <= 0 or size > 10_000:
        raise ValueError("Solicitud no válida.")
    payload = json.loads(request.rfile.read(size).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Solicitud no válida.")
    return payload


def _repository_from_environment() -> SupabaseAdminRepository:
    url = os.getenv("SUPABASE_URL", "").strip()
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise RuntimeError("Falta la configuración de Supabase.")
    return SupabaseAdminRepository(url, secret_key)

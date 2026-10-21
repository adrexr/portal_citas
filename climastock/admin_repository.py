"""Private Supabase queries used by the operational dashboard."""

from __future__ import annotations

import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID


class AdminRepositoryError(RuntimeError):
    """Raised when the private dashboard cannot access its data."""


class SupabaseAdminRepository:
    """Server-side queries for appointments and WhatsApp conversations."""

    def __init__(self, url: str, secret_key: str, opener: Callable = urlopen) -> None:
        self._url = url.rstrip("/")
        self._secret_key = secret_key
        self._opener = opener

    def list_messages(self, status: str = "", limit: int = 100) -> list[dict]:
        filters = [("select", "id,sender_phone,message_type,message_text,sent_at,received_at,status")]
        if status:
            filters.append(("status", f"eq.{status}"))
        filters.extend((("order", "sent_at.desc"), ("limit", str(limit))))
        rows = self._request("GET", "whatsapp_messages", f"?{urlencode(filters)}")
        return _rows(rows)

    def list_appointments(self, date: str) -> list[dict]:
        filters = [
            ("select", "id,patient_name,service,professional,starts_at,status"),
            ("starts_at", f"gte.{date}T00:00"),
            ("starts_at", f"lt.{date}T23:59:59"),
            ("order", "starts_at.asc"),
        ]
        return _rows(self._request("GET", "appointments", f"?{urlencode(filters)}"))

    def update_message_status(self, message_id: str, status: str) -> dict:
        try:
            identifier = str(UUID(message_id))
        except (ValueError, AttributeError) as error:
            raise ValueError("El mensaje no es válido.") from error
        rows = self._request(
            "PATCH", "whatsapp_messages", f"?{urlencode({'id': f'eq.{identifier}'})}", {"status": status},
        )
        if len(rows) != 1:
            raise ValueError("No encontramos ese mensaje.")
        return rows[0]

    def _request(self, method: str, table: str, query: str, payload: dict | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "apikey": self._secret_key,
            "Authorization": f"Bearer {self._secret_key}",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self._url}/rest/v1/{table}{query}", data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=10) as response:
                body = response.read()
        except HTTPError as error:
            body = error.read()
            raise AdminRepositoryError("No fue posible consultar el panel.") from error
        except (URLError, TimeoutError) as error:
            raise AdminRepositoryError("No fue posible conectar con la base de datos.") from error
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AdminRepositoryError("La base de datos devolvió una respuesta no válida.") from error


def _rows(value: object) -> list[dict]:
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise AdminRepositoryError("La base de datos devolvió una respuesta no válida.")
    return value

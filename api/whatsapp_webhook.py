"""Webhook endpoint for incoming WhatsApp Cloud API messages."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from climastock.whatsapp_repository import SupabaseWhatsAppRepository, WhatsAppRepositoryError


def verify_webhook_request(query: dict[str, list[str]], verify_token: str) -> str | None:
    """Return Meta's challenge only for a valid webhook subscription request."""
    mode = query.get("hub.mode", [""])[0]
    token = query.get("hub.verify_token", [""])[0]
    challenge = query.get("hub.challenge", [""])[0]
    if mode != "subscribe" or not challenge or not hmac.compare_digest(token, verify_token):
        return None
    return challenge


def extract_incoming_messages(payload: dict) -> list[dict[str, str | None]]:
    """Extract only the message fields needed by the application from Meta's event."""
    extracted: list[dict[str, str | None]] = []
    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []):
            value = change.get("value", {}) if isinstance(change, dict) else {}
            metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
            phone_number_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            for message in value.get("messages", []) if isinstance(value, dict) else []:
                parsed = _parse_message(message, phone_number_id)
                if parsed is not None:
                    extracted.append(parsed)
    return extracted


def _parse_message(message: object, phone_number_id: object) -> dict[str, str | None] | None:
    if not isinstance(message, dict):
        return None
    message_id = message.get("id")
    sender_phone = message.get("from")
    message_type = message.get("type")
    timestamp = message.get("timestamp")
    if not all(isinstance(value, str) and value for value in (message_id, sender_phone, message_type, timestamp)):
        return None
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), tz=UTC).isoformat()
    except (OverflowError, TypeError, ValueError):
        return None
    content = message.get(message_type, {})
    text = content.get("body") if message_type == "text" and isinstance(content, dict) else None
    return {
        "provider_message_id": message_id,
        "sender_phone": sender_phone,
        "recipient_phone_number_id": phone_number_id if isinstance(phone_number_id, str) else None,
        "message_type": message_type,
        "message_text": text if isinstance(text, str) else None,
        "sent_at": sent_at,
    }


def is_valid_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Validate the X-Hub-Signature-256 sent by Meta."""
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


class handler(BaseHTTPRequestHandler):
    """Vercel webhook handler available at /api/whatsapp_webhook."""

    def do_GET(self) -> None:
        token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        challenge = verify_webhook_request(parse_qs(urlparse(self.path).query), token) if token else None
        if challenge is None:
            self._send(HTTPStatus.FORBIDDEN, "text/plain; charset=utf-8", "Verificación rechazada")
            return
        self._send(HTTPStatus.OK, "text/plain; charset=utf-8", challenge)

    def do_POST(self) -> None:
        app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not app_secret or size <= 0 or size > 100_000:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": "Solicitud no válida."})
            return
        body = self.rfile.read(size)
        if not is_valid_signature(body, self.headers.get("X-Hub-Signature-256", ""), app_secret):
            self._send_json(HTTPStatus.UNAUTHORIZED, {"success": False, "error": "Firma inválida."})
            return
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError
            repository = _repository_from_environment()
            repository.save_many(extract_incoming_messages(payload))
        except (ValueError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": "Solicitud no válida."})
            return
        except (RuntimeError, WhatsAppRepositoryError):
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"success": False, "error": "Servicio no disponible."})
            return
        self._send_json(HTTPStatus.OK, {"success": True})

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False))

    def _send(self, status: HTTPStatus, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _repository_from_environment() -> SupabaseWhatsAppRepository:
    url = os.getenv("SUPABASE_URL", "").strip()
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise RuntimeError("Falta la configuración de Supabase.")
    return SupabaseWhatsAppRepository(url, secret_key)

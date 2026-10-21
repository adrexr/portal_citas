"""Supabase persistence for incoming WhatsApp messages."""

from __future__ import annotations

import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WhatsAppRepositoryError(RuntimeError):
    """Raised when an incoming message cannot be persisted."""


class SupabaseWhatsAppRepository:
    """Writes incoming messages through Supabase's service-role REST API."""

    def __init__(self, url: str, secret_key: str, opener: Callable = urlopen) -> None:
        self._url = url.rstrip("/")
        self._secret_key = secret_key
        self._opener = opener

    def save_many(self, messages: list[dict[str, str | None]]) -> None:
        if not messages:
            return
        request = Request(
            f"{self._url}/rest/v1/whatsapp_messages?on_conflict=provider_message_id",
            data=json.dumps(messages).encode("utf-8"),
            headers={
                "apikey": self._secret_key,
                "Authorization": f"Bearer {self._secret_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=10):
                return
        except HTTPError as error:
            raise WhatsAppRepositoryError("No fue posible guardar el mensaje de WhatsApp.") from error
        except URLError as error:
            raise WhatsAppRepositoryError("No fue posible conectar con la base de datos.") from error

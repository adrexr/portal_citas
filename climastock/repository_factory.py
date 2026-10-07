"""Select the configured appointment persistence implementation."""

from __future__ import annotations

import os
from pathlib import Path

from climastock.booking import AppointmentRepository
from climastock.supabase_repository import SupabaseAppointmentRepository


def repository_from_environment() -> AppointmentRepository | SupabaseAppointmentRepository:
    """Use Supabase when configured, otherwise preserve local SQLite development."""
    url = os.getenv("SUPABASE_URL", "").strip()
    secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url and not secret_key:
        return AppointmentRepository()
    if not url:
        raise RuntimeError("Falta configurar SUPABASE_URL.")
    if not secret_key:
        raise RuntimeError("Falta configurar SUPABASE_SECRET_KEY.")
    return SupabaseAppointmentRepository(url, secret_key)


def load_environment_file() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for line_number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"Configuración inválida en .env, línea {line_number}.")
        name, value = stripped.split("=", 1)
        name = name.strip()
        if name not in {"SUPABASE_URL", "SUPABASE_SECRET_KEY"}:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)

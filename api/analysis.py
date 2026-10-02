"""Vercel Function: returns a private, auditable clinical capacity plan."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from climastock.analyzer import CapacityRequest, plan_clinical_capacity


def build_capacity_payload(query: dict[str, list[str]]) -> dict:
    """Build a capacity plan without external calls or patient data."""
    request = CapacityRequest(
        service=_parameter(query, "service"),
        scheduled_appointments=int(_parameter(query, "appointments")),
        clinicians_on_duty=int(_parameter(query, "clinicians")),
        consultation_minutes=int(_parameter(query, "minutes")),
        available_rooms=int(_parameter(query, "rooms")),
    )
    plan = plan_clinical_capacity(request)
    return {
        "service": request.service,
        "planning_window": "Turno de 8 horas",
        "plan": {
            "status": plan.status,
            "total_capacity": plan.total_capacity,
            "utilization_percent": plan.utilization_percent,
            "overflow_appointments": plan.overflow_appointments,
            "additional_clinicians_needed": plan.additional_clinicians_needed,
            "reason": plan.reason,
        },
    }


class handler(BaseHTTPRequestHandler):
    """Vercel discovers this class automatically at /api/analysis."""

    def do_GET(self) -> None:
        try:
            payload = build_capacity_payload(parse_qs(urlparse(self.path).query))
            self._send_json(HTTPStatus.OK, payload)
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def _parameter(query: dict[str, list[str]], name: str) -> str:
    value = query.get(name, [""])[0].strip()
    if not value:
        raise ValueError(f"El campo '{name}' es obligatorio.")
    return value

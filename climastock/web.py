"""Dependency-free local server for ClinicaFlow."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from api.analysis import build_capacity_payload
from api.appointments import (cancel_appointment_payload, create_appointment_payload,
                              list_appointments_payload, reschedule_appointment_payload)
from climastock.booking import AppointmentConflictError, AppointmentRepository


class ClinicaFlowHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        route = urlparse(self.path)
        if route.path == "/":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", _dashboard_html())
            return
        if route.path == "/api/analysis":
            self._handle_analysis(parse_qs(route.query))
            return
        if route.path == "/api/appointments":
            self._handle_appointments(route)
            return
        self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", "Ruta no encontrada")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/appointments":
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", "Ruta no encontrada")
            return
        try:
            payload = self._read_json()
            self._send_json(HTTPStatus.CREATED, create_appointment_payload(payload, AppointmentRepository()))
        except AppointmentConflictError as error:
            self._send_json(HTTPStatus.CONFLICT, {"success": False, "error": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})

    def do_DELETE(self) -> None:
        route = urlparse(self.path)
        if route.path != "/api/appointments":
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", "Ruta no encontrada")
            return
        try:
            appointment_id = parse_qs(route.query).get("id", [""])[0]
            self._send_json(HTTPStatus.OK, cancel_appointment_payload(appointment_id, AppointmentRepository()))
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})

    def do_PATCH(self) -> None:
        if urlparse(self.path).path != "/api/appointments":
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", "Ruta no encontrada")
            return
        try:
            payload = self._read_json()
            appointment_id = str(payload.get("id", ""))
            starts_at = str(payload.get("starts_at", ""))
            self._send_json(HTTPStatus.OK, reschedule_appointment_payload(appointment_id, starts_at, AppointmentRepository()))
        except AppointmentConflictError as error:
            self._send_json(HTTPStatus.CONFLICT, {"success": False, "error": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})

    def _handle_appointments(self, route) -> None:
        try:
            date = parse_qs(route.query).get("date", [""])[0]
            self._send_json(HTTPStatus.OK, list_appointments_payload(date, AppointmentRepository()))
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"success": False, "error": str(error)})

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 10_000:
            raise ValueError("La solicitud no es válida.")
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("La solicitud no es válida.")
        return payload

    def _handle_analysis(self, query: dict[str, list[str]]) -> None:
        try:
            self._send_json(HTTPStatus.OK, build_capacity_payload(query))
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _send_json(self, status: HTTPStatus, data: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False))

    def _send(self, status: HTTPStatus, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args) -> None:
        return


def run_server(port: int = 8000) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), ClinicaFlowHandler)
    print(f"ClinicaFlow disponible en http://127.0.0.1:{port}")
    print("Presiona Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


def _dashboard_html() -> str:
    return (Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")

"""Deterministic, non-clinical planning rules for outpatient capacity."""

from dataclasses import dataclass
from math import ceil

SHIFT_MINUTES = 480


@dataclass(frozen=True)
class CapacityRequest:
    service: str
    scheduled_appointments: int
    clinicians_on_duty: int
    consultation_minutes: int
    available_rooms: int


@dataclass(frozen=True)
class CapacityPlan:
    status: str
    total_capacity: int
    utilization_percent: int
    overflow_appointments: int
    additional_clinicians_needed: int
    reason: str


def plan_clinical_capacity(request: CapacityRequest) -> CapacityPlan:
    """Plan appointment capacity for one service; never assesses patients or care."""
    _validate_request(request)
    appointments_per_clinician = SHIFT_MINUTES // request.consultation_minutes
    appointments_per_room = SHIFT_MINUTES // request.consultation_minutes
    clinician_capacity = request.clinicians_on_duty * appointments_per_clinician
    room_capacity = request.available_rooms * appointments_per_room
    total_capacity = min(clinician_capacity, room_capacity)
    overflow = max(0, request.scheduled_appointments - total_capacity)
    utilization = ceil(request.scheduled_appointments / total_capacity * 100)
    additional = max(0, ceil(request.scheduled_appointments / appointments_per_clinician) - request.clinicians_on_duty)
    status, reason = _operational_status(utilization, overflow)
    return CapacityPlan(status, total_capacity, utilization, overflow, additional, reason)


def _operational_status(utilization: int, overflow: int) -> tuple[str, str]:
    if overflow:
        return "CRÍTICA", "La agenda supera la capacidad estimada; activa refuerzo o redistribución de turnos."
    if utilization >= 85:
        return "ATENCIÓN", "La agenda tiene poco margen operativo; confirma disponibilidad antes de abrir más cupos."
    return "ESTABLE", "La agenda conserva margen operativo para absorber variaciones del turno."


def _validate_request(request: CapacityRequest) -> None:
    if not request.service.strip():
        raise ValueError("El servicio es obligatorio.")
    values = (request.scheduled_appointments, request.clinicians_on_duty, request.consultation_minutes, request.available_rooms)
    if request.scheduled_appointments < 0 or any(value <= 0 for value in values[1:]):
        raise ValueError("Las citas deben ser cero o más; personal, duración y consultorios deben ser positivos.")

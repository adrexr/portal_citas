import unittest
from http.server import BaseHTTPRequestHandler

from api.analysis import build_capacity_payload, handler
from climastock.analyzer import CapacityRequest, plan_clinical_capacity


class CapacityPlanningTests(unittest.TestCase):
    def test_identifies_when_a_service_needs_an_extra_clinician(self):
        request = CapacityRequest(
            service="Consulta externa", scheduled_appointments=42, clinicians_on_duty=2,
            consultation_minutes=30, available_rooms=3,
        )

        plan = plan_clinical_capacity(request)

        self.assertEqual(plan.status, "CRÍTICA")
        self.assertEqual(plan.total_capacity, 32)
        self.assertEqual(plan.overflow_appointments, 10)
        self.assertEqual(plan.additional_clinicians_needed, 1)

    def test_marks_a_balanced_service_as_stable(self):
        request = CapacityRequest(
            service="Vacunación", scheduled_appointments=20, clinicians_on_duty=2,
            consultation_minutes=20, available_rooms=3,
        )

        plan = plan_clinical_capacity(request)

        self.assertEqual(plan.status, "ESTABLE")
        self.assertEqual(plan.overflow_appointments, 0)
        self.assertEqual(plan.additional_clinicians_needed, 0)

    def test_rejects_an_invalid_operational_request(self):
        request = CapacityRequest(
            service="", scheduled_appointments=-1, clinicians_on_duty=0,
            consultation_minutes=0, available_rooms=0,
        )

        with self.assertRaises(ValueError):
            plan_clinical_capacity(request)


class VercelFunctionTests(unittest.TestCase):
    def test_api_function_is_a_vercel_compatible_http_handler(self):
        self.assertTrue(issubclass(handler, BaseHTTPRequestHandler))

    def test_api_returns_an_auditable_capacity_plan(self):
        payload = build_capacity_payload({
            "service": ["Consulta externa"], "appointments": ["42"], "clinicians": ["2"],
            "minutes": ["30"], "rooms": ["3"],
        })

        self.assertEqual(payload["service"], "Consulta externa")
        self.assertEqual(payload["plan"]["status"], "CRÍTICA")
        self.assertEqual(payload["plan"]["overflow_appointments"], 10)

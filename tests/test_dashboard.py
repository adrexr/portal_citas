"""Lightweight contracts for the dependency-free ClinicaFlow dashboard."""

import unittest
from pathlib import Path


class DashboardExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dashboard = Path("index.html").read_text(encoding="utf-8")

    def test_exposes_accessible_agenda_controls_and_rescheduling(self) -> None:
        self.assertIn('id="appointment-search"', self.dashboard)
        self.assertIn('id="professional-filter"', self.dashboard)
        self.assertIn('id="reschedule-dialog"', self.dashboard)
        self.assertIn("method: 'PATCH'", self.dashboard)
        self.assertIn('aria-modal="true"', self.dashboard)

    def test_supports_theme_preference_and_reduced_motion(self) -> None:
        self.assertIn('id="theme-toggle"', self.dashboard)
        self.assertIn("localStorage.setItem('clinicaflow-theme'", self.dashboard)
        self.assertIn('@media (prefers-reduced-motion: reduce)', self.dashboard)

    def test_keeps_feedback_and_safe_rendering_for_dynamic_content(self) -> None:
        self.assertIn('aria-live="polite"', self.dashboard)
        self.assertIn('const escapeHtml', self.dashboard)
        self.assertIn('button.disabled = busy', self.dashboard)
        self.assertIn('button.textContent = busy ? text : button.dataset.label', self.dashboard)

    def test_theme_storage_failure_does_not_prevent_loading_the_agenda(self) -> None:
        self.assertIn('try { savedTheme = localStorage.getItem', self.dashboard)
        self.assertIn('catch (_error) {', self.dashboard)


if __name__ == "__main__":
    unittest.main()

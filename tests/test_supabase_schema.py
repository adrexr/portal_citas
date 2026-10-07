"""Guardrails for the deployable Supabase schema migration."""

import unittest
from pathlib import Path


class SupabaseSchemaTests(unittest.TestCase):
    def test_schema_protects_appointments_and_prevents_overlapping_slots(self) -> None:
        schema = Path("supabase/migrations/202610060001_create_appointments.sql").read_text(encoding="utf-8")

        self.assertIn("create table public.appointments", schema)
        self.assertIn("enable row level security", schema)
        self.assertIn("revoke all on table public.appointments from anon, authenticated", schema)
        self.assertIn("exclude using gist", schema)
        self.assertIn("status = 'confirmada'", schema)


if __name__ == "__main__":
    unittest.main()

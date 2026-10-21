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

    def test_whatsapp_schema_protects_message_data_and_deduplicates_provider_events(self) -> None:
        schema = Path("supabase/migrations/202610210001_create_whatsapp_messages.sql").read_text(encoding="utf-8")

        self.assertIn("create table public.whatsapp_messages", schema)
        self.assertIn("provider_message_id text not null unique", schema)
        self.assertIn("enable row level security", schema)
        self.assertIn("revoke all on table public.whatsapp_messages from anon, authenticated", schema)
        self.assertIn("grant all on table public.whatsapp_messages to service_role", schema)

    def test_message_workflow_adds_only_known_statuses(self) -> None:
        schema = Path("supabase/migrations/202610210002_add_whatsapp_message_status.sql").read_text(encoding="utf-8")

        self.assertIn("add column status text not null default 'nuevo'", schema)
        self.assertIn("check (status in ('nuevo', 'respondido', 'cita_creada'))", schema)


if __name__ == "__main__":
    unittest.main()

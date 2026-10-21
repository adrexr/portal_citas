-- Workflow state for the private WhatsApp inbox.
alter table public.whatsapp_messages
  add column status text not null default 'nuevo'
  check (status in ('nuevo', 'respondido', 'cita_creada'));

create index whatsapp_messages_status_sent_at_idx
  on public.whatsapp_messages (status, sent_at desc);

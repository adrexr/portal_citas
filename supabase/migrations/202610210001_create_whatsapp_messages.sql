-- Incoming WhatsApp messages. Apply after the appointments migration.
create table public.whatsapp_messages (
  id uuid primary key default gen_random_uuid(),
  provider_message_id text not null unique check (char_length(provider_message_id) between 1 and 255),
  sender_phone text not null check (char_length(sender_phone) between 1 and 32),
  recipient_phone_number_id text,
  message_type text not null check (char_length(message_type) between 1 and 50),
  message_text text,
  sent_at timestamptz not null,
  received_at timestamptz not null default now()
);

create index whatsapp_messages_sent_at_idx on public.whatsapp_messages (sent_at desc);
create index whatsapp_messages_sender_phone_sent_at_idx on public.whatsapp_messages (sender_phone, sent_at desc);

alter table public.whatsapp_messages enable row level security;
revoke all on table public.whatsapp_messages from anon, authenticated;
grant all on table public.whatsapp_messages to service_role;

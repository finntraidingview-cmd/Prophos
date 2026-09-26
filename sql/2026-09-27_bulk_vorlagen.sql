-- 2026-09-27: Zentrale Vorlagen fürs Bulk-Hinzufügen von Konten, für alle IDs nutzbar (Auftrag Koordination B11 für F12).
-- Lesen: jeder eingeloggte Nutzer (RLS select für authenticated). Schreiben NUR über app.py POST /admin/bulk-vorlagen
-- (Service-Key, Admin-Prüfung über ADMIN_EMAILS) — keine Schreib-Policy für Clients. Die persönliche Tabelle
-- account_templates bleibt unberührt. Keine Start-Zeilen (Werte klärt Finn).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
create table if not exists public.bulk_vorlagen (
  id                   uuid primary key default gen_random_uuid(),
  name                 text not null unique,
  firm                 text,
  account_type         text,
  account_size         numeric,
  starting_balance     numeric,
  max_drawdown         numeric,
  max_daily_drawdown   numeric,
  max_loss_per_trade   numeric,
  max_profit_per_trade numeric,
  purchase_cost        numeric,
  purchase_ccy         text default 'EUR',
  wd_farm              boolean default false,
  goal_kind            text,
  goal_target          int,
  name_template        text,
  plattform            text,
  muster_titel         text,
  muster_praefix       text,
  aktiv                boolean default true,
  sortierung           int default 0,
  updated_at           timestamptz default now(),
  updated_by           uuid
);
alter table public.bulk_vorlagen enable row level security;
drop policy if exists bulk_vorlagen_lesen on public.bulk_vorlagen;
create policy bulk_vorlagen_lesen on public.bulk_vorlagen for select to authenticated using (true);

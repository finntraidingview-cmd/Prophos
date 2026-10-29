-- ADMIN-VOLL (30.10.2026, Master/Finn: Finns Tages-Login „Finn + Pascal" steht nicht in ADMIN_EMAILS, Finn will keine Railway-Variablen
-- pflegen): enge Freigabe NUR für die Admin-Reiter-Aktionen „Payout erhalten" (PATCH /admin/payout-erhalten) und „Hedge-Freigabe"
-- (GET/POST /admin/auto-plan/hedge-freigabe, ✓ bestätigen gibt den Hedge frei). Eine Zeile = dieser Login darf diese Aktionen wie ein Admin,
-- sonst nichts — Rechnungen, Ausgleichen, Bot-Schalter bleiben bei ADMIN_EMAILS. Nicht über auto_plan_regeln.user_ids: dort stehen alle
-- Kunden-IDs (Master-Stopp für 95197c02).
-- Gate im Backend: _admin_voll (app.py), 60 s gemerkt; Tabelle fehlt → leer (nie still freigeben); der Login darf im Admin nicht
-- eingeschränkt sein (admin_sicht_lesen → None: kein Verwalter, kein Gruppen-Mitglied, nicht „nur eigene").
-- Lesen/Schreiben nur Service-Key (RLS an, keine Policy) — kein Login kann sich selbst eintragen. Keine E-Mail im Repo, nur user_ids.

create table if not exists public.admin_voll (
  user_id uuid primary key references auth.users(id) on delete cascade,
  seit    timestamptz not null default now()
);

alter table public.admin_voll enable row level security;

-- Befüllung wie die Mail-Leser (heute „Finn + Pascal" und „Pascal")
insert into public.admin_voll (user_id) select user_id from public.admin_mail_leser on conflict do nothing;

-- Weitere: eine Zeile mehr, keine Code-Änderung. Entziehen:
-- delete from public.admin_voll where user_id = '<uuid>';

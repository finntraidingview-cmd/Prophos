-- AUFTRAG (05.10.2026): Wochenauftrag je Firma (Soll-Käufe pro Tag, ID-Liste, Ziel) für den Admin-Reiter „Auftrag".
-- Eine Zeile (id = 1), plan = {"gesamt": [min, max], "firmen": [{"label", "firm", "soll": [min, max], "ziel", "ids": [Anzeigename, …]}]}.
-- gesamt (optional) = Soll-Käufe pro Tag über alle Firmen; fehlt es, gilt die Summe der Firmen-Spannen.
-- Die ID-Namen stehen bewusst NUR hier in der DB, nie im Code (Repo ist öffentlich). firm = Schreibweise nach _firm_norm.
-- Lesen nur über /admin/auftrag (Service-Key) — RLS an, keine Policy.
create table if not exists public.auftrag_plan (
  id smallint primary key default 1 check (id = 1),
  plan jsonb not null default '{"firmen": []}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.auftrag_plan enable row level security;

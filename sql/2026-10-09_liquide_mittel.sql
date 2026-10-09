-- LIQUIDE MITTEL (09.10.2026, Slave-Terminal 4 — Auftrag Pascal über Finn, Vertrag .claude/master/auftraege/liquide-vertrag.md)
--
-- Kunden-Töpfe aus Google Sheets (je Kunde ein Sheet „Transaktion, Betrag EUR, Datum", Zeile 2 Spalte B = Kontostand) und das
-- Kunden-Flag je Person für die Übersicht „Liquide Mittel" im Admin-Reiter Wallets. Neue Tabellen, nichts Bestehendes geändert.
-- Zugriff NUR über das Backend (app.py /admin/liquide*, Service-Key, Gate Voll-Admin): RLS an, keine Policies, keine Rechte für
-- anon/authenticated — wie die Admin-Übersichten (id_gruppen_uebersicht). Kontostände von Kunden gehören nicht in den Browser-Zugriff.
-- Die Start-Sheets trägt das Slave-Terminal nach dem Einspielen per Insert ein (nicht in dieser Datei: keine Sheet-IDs/Namen im Repo).
-- Wiederholbar (if not exists).

create table if not exists public.kunden_sheets (
  id          uuid primary key default gen_random_uuid(),
  person_uid  uuid,
  person_name text not null,
  sheet_id    text not null unique,
  aktiv       boolean not null default true,
  created_at  timestamptz default now()
);

-- eine Zeile je Sheet und Dubai-Tag, beim Abruf überschrieben; bei Fehler kontostand null und der Grund in fehler (nie stumm 0)
create table if not exists public.bank_staende (
  person_uid     uuid,
  sheet_id       text not null,
  day            date not null,
  kontostand     numeric,
  einzahlungen   numeric,
  kaeufe         numeric,
  payouts        numeric,
  an_uns         numeric,
  letzte_buchung date,
  diff           numeric,
  fehler         text,
  geholt_at      timestamptz,
  primary key (sheet_id, day)
);

-- Kunden-Flag je Person; fehlt die Zeile: Kunde = true, außer den Admins (ADMIN_EMAILS) = false (das rechnet app.py)
create table if not exists public.liq_personen (
  user_id    uuid primary key,
  ist_kunde  boolean not null,
  updated_at timestamptz default now()
);

alter table public.kunden_sheets enable row level security;
alter table public.bank_staende  enable row level security;
alter table public.liq_personen  enable row level security;

revoke all on public.kunden_sheets from public, anon, authenticated;
revoke all on public.bank_staende  from public, anon, authenticated;
revoke all on public.liq_personen  from public, anon, authenticated;
grant all on public.kunden_sheets to service_role;
grant all on public.bank_staende  to service_role;
grant all on public.liq_personen  to service_role;

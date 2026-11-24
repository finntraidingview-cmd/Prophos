-- ============================================================================
-- Prophos: BK6 Kontoauszüge + KI-Abgleich (25.11.2026) — NICHT eingespielt (Prüfer-Pflicht: neue Tabelle, Bucket, Schreiblogik)
--
-- Finn: „Ja zum Kontoauszug-Upload". Konstrukt side-session-notes/…/2026-11-25_BK6_kontoauszug_konstrukt.md, Standardwerte vom Master:
-- Auszüge 12 Monate aufbewahren (bank_app.py löscht ältere Datei + Zeile), Erinnerung nur in der Liste (kein Alarm), Datum ±3 Tage.
--
--   storage „kontoauszuege"   privater Bucket, PDF/CSV ≤ 10 MB. KEINE Policies auf storage.objects für diesen Bucket → nur der
--                             Service-Key (Railway, bank_app.py) lädt hoch, löscht und signiert 5-Minuten-Links.
--   bank_auszuege             je hochgeladenem Auszug eine Zeile: Konto, Datei, Zeitraum, Endsaldo, ausgelesene Zeilen (jsonb).
--   bank_buchungen.auszug_id  aus einem Auszug übernommene Buchung (quelle 'auszug'); on delete set null.
--
-- RLS an, keine Policy für Logins, Rechte anon/authenticated entzogen — wie bank_konten/bank_buchungen (BK1). Keine IBAN in dieser Datei.
-- Idempotent.
-- ============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('kontoauszuege', 'kontoauszuege', false, 10485760, array['application/pdf', 'text/csv', 'text/plain'])
on conflict (id) do nothing;

create table if not exists public.bank_auszuege (
  id              uuid primary key default gen_random_uuid(),
  konto_id        uuid not null references public.bank_konten(id) on delete cascade,
  datei_pfad      text,                                   -- <konto_id>/<id>.<pdf|csv> im Bucket; null = Datei schon gelöscht
  datei_typ       text not null check (datei_typ in ('pdf', 'csv')),
  datei_name      text,
  status          text not null default 'hochgeladen' check (status in ('hochgeladen', 'liest', 'gelesen', 'fehler')),
  fehler          text,
  von             date,
  bis             date,
  endsaldo        numeric,
  waehrung        text,
  zeilen          jsonb not null default '[]'::jsonb,     -- [{datum, betrag, text, gegenseite}] — ohne IBAN der Gegenseite
  vorschlag       jsonb,                                  -- {bank, iban, inhaber} aus dem Auszugskopf, nur Vorschlag (nie automatisch gesetzt)
  uebersprungen   int not null default 0,                 -- CSV-Zeilen, die nicht lesbar waren (wird angezeigt, nie still)
  hochgeladen_von text,
  created_at      timestamptz not null default now(),
  gelesen_at      timestamptz
);
alter table public.bank_auszuege add column if not exists uebersprungen int not null default 0;
create index if not exists bank_auszuege_konto_idx on public.bank_auszuege (konto_id, created_at desc);

alter table public.bank_buchungen add column if not exists auszug_id uuid references public.bank_auszuege(id) on delete set null;
-- Zeile des Auszugs, aus der die Buchung übernommen wurde: einmal je Zeile (zwei Klicks/Tabs → 409 statt Doppelbuchung) und fester Partner im Abgleich
alter table public.bank_buchungen add column if not exists auszug_zeile int;
create unique index if not exists bank_buchungen_auszug_zeile_uq on public.bank_buchungen (auszug_id, auszug_zeile)
  where auszug_id is not null and auszug_zeile is not null;
alter table public.bank_buchungen drop constraint if exists bank_buchungen_quelle_check;
alter table public.bank_buchungen add constraint bank_buchungen_quelle_check check (quelle in ('hand', 'sheet', 'auszug'));

alter table public.bank_auszuege enable row level security;
revoke all on public.bank_auszuege from anon, authenticated;
grant all on public.bank_auszuege to service_role;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.bank_auszuege to backup_reader';
    execute 'drop policy if exists backup_reader_select on public.bank_auszuege';
    execute 'create policy backup_reader_select on public.bank_auszuege for select to backup_reader using (true)';
  end if;
end $$;

-- Kontrolle:
-- select id, public, file_size_limit, allowed_mime_types from storage.buckets where id = 'kontoauszuege';
-- select relrowsecurity from pg_class where oid = 'public.bank_auszuege'::regclass;

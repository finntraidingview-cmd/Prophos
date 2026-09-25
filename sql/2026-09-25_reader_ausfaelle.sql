-- 2026-09-25: Protokoll des Reader-Wachhunds (app.py, READER-WACHT).
-- Finn: „Erstelle einen Agent, der die nächsten 24 Stunden den Reader überwacht, damit es keine
-- Ausfälle gibt. Wenn es Ausfälle gibt, schick über die Prophos-Benachrichtigung eine Nachricht an
-- mein Handy." Der Wachhund läuft auf Railway und schreibt je Vorfall eine Zeile:
--   art          'feed'   = kein frischer Kurs in tv_kurse > 120 s bei offenem CME-Markt
--                'kerzen' = Feed frisch, aber jüngste Kerze in tv_kurs_1m > 3 min alt
--   von / bis    Beginn / Ende (bis NULL = läuft noch; beim Neustart übernimmt der Wachhund
--                die offene Zeile, damit derselbe Ausfall nicht doppelt aufs Handy kommt)
--   gemeldet     Zahl der verschickten Push-Meldungen zu diesem Vorfall
-- Lesen für angemeldete Nutzer (Anzeige), Schreiben nur mit dem Service-Key (keine Policy dafür).
-- Ohne diese Tabelle läuft der Wachhund trotzdem — nur das Protokoll fehlt.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
create table if not exists public.reader_ausfaelle (
  id           bigserial primary key,
  art          text not null check (art in ('feed', 'kerzen')),
  von          timestamptz not null,
  bis          timestamptz,
  dauer_s      integer,
  letzter_kurs numeric,
  pc           text,
  gemeldet     integer not null default 0,
  created_at   timestamptz not null default now()
);
create index if not exists reader_ausfaelle_von_idx on public.reader_ausfaelle (von desc);
create index if not exists reader_ausfaelle_offen_idx on public.reader_ausfaelle (art) where bis is null;

alter table public.reader_ausfaelle enable row level security;
drop policy if exists "reader_ausfaelle read" on public.reader_ausfaelle;
create policy "reader_ausfaelle read" on public.reader_ausfaelle for select to authenticated using (true);

-- MINI-FINN MELDET AN FINN (Finn 27.10.2026 ~16:00 Dubai: „Wenn wirklich ein echter Fehler da ist und der Chat nichts machen kann (passiert
-- oft), soll er sagen: ‚Okay, tut mir leid, das gebe ich direkt an Finn weiter.' Ich habe dann in Claude eine Routine, die die ganze Zeit
-- abfragt, wo die Fehler von Mini-Finn ankommen, damit ich sie fixen kann.“)
--
-- Eine Zeile je Meldung. Mini-Finn legt sie über das Werkzeug an_finn_melden an (support_app.py), ohne Bestätigen-Klick (ändert nichts am
-- Handel). Gleicher Nutzer + gleiche Ursache (schluessel) binnen 30 min → dieselbe Zeile (anzahl + 1, Nachtrag in beschreibung).
-- Anders als support_log NICHT maskiert: Finn braucht Konto-/Plan-IDs zum Fixen. Passwörter/Tokens entfernt der Server vor dem Schreiben.
-- RLS an, KEINE Policy → nur das Backend (Service-Key) und Finns Routine (Supabase-Zugang) lesen/schreiben. Idempotent.
-- Anleitung für die Routine: .claude/support-meldungen.md

create table if not exists public.support_meldung (
  id               bigserial primary key,
  at               timestamptz not null default now(),
  aktualisiert_at  timestamptz not null default now(),
  user_id          uuid,
  unterhaltung_id  uuid,
  kategorie        text not null default 'unklar' check (kategorie in ('bug', 'fehlermeldung', 'wunsch', 'unklar')),
  titel            text not null,
  beschreibung     text,                          -- was der Nutzer wollte, was passiert ist, was Mini-Finn geprüft hat (+ Nachträge)
  belege           jsonb not null default '{}'::jsonb,   -- plan_id, konto, pc, fehlertext, geprüfte Werkzeuge, bilder (Pfade im Bucket)
  schluessel       text,                          -- normierte Ursache fürs Zusammenfassen
  anzahl           integer not null default 1,
  status           text not null default 'neu' check (status in ('neu', 'in_arbeit', 'erledigt', 'verworfen')),
  erledigt_at      timestamptz,
  notiz            text                           -- Finn / Routine: was gefixt wurde (Commit, Version)
);
create index if not exists support_meldung_status_idx on public.support_meldung (status, at desc);
create index if not exists support_meldung_dedupe_idx on public.support_meldung (user_id, schluessel, at desc);

alter table public.support_meldung enable row level security;

-- Kontrolle:
-- select id, to_char(at at time zone 'Asia/Dubai', 'DD.MM. HH24:MI') um, kategorie, titel, anzahl, status from public.support_meldung
--  where status in ('neu', 'in_arbeit') order by at;

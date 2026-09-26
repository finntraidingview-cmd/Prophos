-- 2026-09-26: Updater-Diagnose des TV-Readers je PC (Auftrag Koordination B9). Anlass: auf pc-usq1i6 kam Reader 0.9.6 per
-- Selbst-Update nicht an, obwohl dieselbe 0.9.5-Datei auf dem Mac in 61 s tauschte — die Ursache stand nur im
-- Reader-Fenster. Ab Reader 0.9.7 meldet der Reader über POST https://web-production-bec81.up.railway.app/reader-diagnose/<kennung>:
--   rolle 'aufsicht' (alle 5 min nach jedem Update-Check + beim Start): Version, PID, letzter Check, geprüfte Kennung (sha),
--     sha_fehler (Netz/SSL), wartendes Update, gesperrte Kennungen, letzter Tausch (bewiesen?), Fehler mit Exception-Text,
--     letzte 8 Meldungen, Python/System, Markt offen;
--   rolle 'kind' (einmal beim Start des Servers): Version, PID, Eltern-PID. Fehlt die Zeile 'aufsicht', läuft kein Updater.
-- kennung = pc_id aus mt5-copier/pc_id.json, sonst 'host-<Rechnername>'. Nur der Service-Key (app.py) schreibt.
-- Lesen: select kennung, rolle, at, diagnose from reader_diagnose order by at desc;
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
create table if not exists public.reader_diagnose (
  kennung   text not null check (kennung ~ '^(pc-[a-z0-9]{4,12}|host-[a-z0-9-]{1,30})$'),
  rolle     text not null check (rolle in ('aufsicht', 'kind')),
  diagnose  jsonb not null,
  at        timestamptz not null default now(),
  primary key (kennung, rolle)
);
alter table public.reader_diagnose enable row level security;

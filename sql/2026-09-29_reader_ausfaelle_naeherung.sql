-- 2026-09-29: reader_ausfaelle protokolliert auch Näherungs-Vorfälle (art 'naeherung').
-- Anlass (Finn 29.09.2026: „wenn MNQ auch nur eine Millisekunde auf einem Preis war, muss es der Radar mitkriegen"):
-- exakt sind nur MNQ-Kerzen aus TradingViews Chart-Serie (tv_kurs_1m.quelle 'ws'). Fehlt der MNQ-Chart im Reader-Chrome,
-- baut der Reader Ersatzkerzen aus Einzelkursen ('ws-tick') — der Wachhund (app.py, READER_WACHT_NAEHERUNG_N) meldet das
-- jetzt per Push und schreibt je Vorfall eine Zeile (wurzel, laut=true, von/bis/dauer_s).
-- app.py läuft ohne diese Datei weiter (dann nur Push + Log, kein Protokoll).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.reader_ausfaelle drop constraint if exists reader_ausfaelle_art_check;
alter table public.reader_ausfaelle add constraint reader_ausfaelle_art_check
  check (art = any (array['feed'::text, 'kerzen'::text, 'update'::text, 'naeherung'::text]));

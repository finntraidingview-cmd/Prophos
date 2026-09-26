-- 2026-09-26: reader_ausfaelle protokolliert auch Reader-Updates (art 'update', Text in notiz).
-- Anlass (Auftrag Koordination B3): reader-server.py spielt neue Versionen seit 0.9.4 selbst ein — nur bei geschlossenem
-- CME-Markt. Der Wachhund (app.py) sieht den Wechsel an echoplus_live.reader_version und schreibt ihn als eigene Zeile
-- (von = bis = Zeitpunkt, pc, notiz 'Reader 0.9.3 → 0.9.4'), damit ein Ausfall kurz nach einem Update sofort zuordenbar ist.
-- app.py läuft ohne diese Datei weiter (dann nur Log-Zeile, kein Protokoll).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.reader_ausfaelle add column if not exists notiz text;
alter table public.reader_ausfaelle drop constraint if exists reader_ausfaelle_art_check;
alter table public.reader_ausfaelle add constraint reader_ausfaelle_art_check
  check (art = any (array['feed'::text, 'kerzen'::text, 'update'::text]));

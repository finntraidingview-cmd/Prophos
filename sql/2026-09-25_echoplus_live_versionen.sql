-- 2026-09-25: echoplus_live um die Versionsstände des Reader-PCs erweitern (reader-server 0.8.1).
-- Anlass: Moritz' PC-Tab meldet sich mit Build .495 alle 5 s, tv_kurse bleibt trotzdem leer —
-- aus der Cloud war nicht zu sehen, ob dort ein reader-server von vor dem Kurs-Feed läuft
-- (Selbst-Update nur beim Start über start-reader.bat) oder ein Userscript < 0.7.0
-- (Tampermonkey prüft nur täglich). Der reader-server gibt jetzt in jeder Antwort
-- reader_version / script_version / script_alter_s; die Brücke (Session „Teste") schreibt
-- die beiden Versionen je PC hierher, der Markt-Kopf zeigt sie.
--   reader_version  Stand der reader-server.py auf dem PC (READER_VERSION, z. B. '0.8.1')
--   script_version  Userscript-Version aus dem letzten POST an den reader-server, null = nie gemeldet
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.echoplus_live
  add column if not exists reader_version text,
  add column if not exists script_version text;
comment on column public.echoplus_live.reader_version is 'reader-server.py READER_VERSION auf dem PC (0.8.1+)';
comment on column public.echoplus_live.script_version is 'tv-reader.user.js Version aus dem letzten POST, null = nie gemeldet';

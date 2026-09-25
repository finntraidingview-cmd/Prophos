-- 2026-09-25: reader_ausfaelle bekommt die Wurzel des Kerzen-Vorfalls und ob er laut (Push) war.
-- Anlass (Befund Koordination 25.09.2026): der Feed-Tab auf pc-usq1i6 wechselte das Chart-Symbol (10:25 UTC nur NQ,
-- 11:44 nur MNQ1!) — je eine Wurzel bekam keine Minutenkerzen mehr (Reader-Fix 0.9.2), und der Wachhund meldete einen
-- „Kerzen fehlen"-Vorfall ohne zu sagen, WELCHE Wurzel. Seitdem: laut (Push) nur die Hauptwurzel MNQ, jede andere
-- Wurzel als leiser Hinweis (laut = false, gemeldet 0). app.py schreibt ohne die Spalten weiter, solange sie fehlen.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.reader_ausfaelle add column if not exists wurzel text;
alter table public.reader_ausfaelle add column if not exists laut boolean not null default true;

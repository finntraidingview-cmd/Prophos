-- 2026-09-25: tv_kurs_1m um die Quelle der Kerze erweitern (reader-server 0.8.4).
-- Finn will NQ und MNQ als Chart, ohne das TradingView-Layout umzubauen: auf Moritz' PC liegt NQ nur
-- in der Watchlist, also gibt es dafür keine Chart-Serie (timescale_update/du), nur Quote-Ticks (qsd).
-- Der reader-server baut für solche Wurzeln Minutenkerzen aus den Ticks (lp, sonst Mitte Bid/Ask);
-- O und C sind exakt, H/L nur so gut wie die Tick-Dichte (Näherung). Damit das Frontend das sagen
-- kann („aus Quote-Ticks, H/L Näherung"), trägt jede Kerze ihre Quelle:
--   quelle  'ws'       Kerze aus TradingViews Chart-Serie (exakt, mit Volumen)
--           'ws-tick'  aus Quote-Ticks gebaut (H/L Näherung, kein Volumen)
--           NULL       Bestand vor 0.8.4 bzw. Tick-Kerzen des Titel-/Legenden-Wegs
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.tv_kurs_1m add column if not exists quelle text;
comment on column public.tv_kurs_1m.quelle is 'ws = Chart-Serie | ws-tick = aus Quote-Ticks (H/L Näherung) | null = Bestand';

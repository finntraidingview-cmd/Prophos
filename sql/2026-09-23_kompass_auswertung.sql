-- 2026-09-23: Kompass-Auswertung (Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder,
-- will sehen wie gut der is"). Je Forecast rechnet der Railway-Sammler aus den NQ-Futures-Kerzen
-- (Yahoo, 5 min, 60 Tage), wie sich der Kurs 1/2/4/8 Stunden nach der Posting-Zeit bewegt hat.
-- t0 = Posting-Zeit (Pascals id ist ein Epoch-Zeitstempel: idea-1790114840 = 22.09.2026 22:07:20 UTC).
-- auswertung = {p0, h1:{p,dp,hit,mfe,mae}, h2:…, h4:…, h8:…, fertig, berechnet_at}
--   dp  = Bewegung in Prozent (positiv = gestiegen), hit = in Forecast-Richtung,
--   mfe = max. Bewegung dafür im Fenster, mae = max. Bewegung dagegen (jeweils Prozent).
alter table public.kompass_forecasts add column if not exists t0 timestamptz;
alter table public.kompass_forecasts add column if not exists auswertung jsonb;
create index if not exists kompass_forecasts_t0 on public.kompass_forecasts (t0 desc);

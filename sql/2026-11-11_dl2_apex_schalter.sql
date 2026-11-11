-- DL2-SCHALTER (Master 11.11.2026 nach Prüfer S7: „Apex ist mit DL2 nicht bitgleich … Finn hat zu Apex noch nicht entschieden“): die DL2-Verschärfungen am
-- Tageslimit — Fusion-Hedge schließt ≥ 100 $ vor dem Daily Loss (geglättete Kante, prophos.html hedgeLiqLevel/ahfWdPaare), WD „ohne SL“ bekommt einen
-- Pflicht-SL 100 $ vor dem Tageslimit (app.py wd_sl_dll_pflicht), kein WD-Plan ohne SL (DL2b, wd_sl_dll_firma) — gelten je liq_regeln-Zeile:
--   dll_schutz = true  → an
--   dll_schutz = false → aus (wie vor DL2: Hedge 5 NQ-Punkte vor dem Tageslimit, WD-Würfel „ohne SL“ bleibt ohne)
--   dll_schutz = NULL  → Standard: an bei art 'tagesstart' (Lucid, FTMO Futures), AUS bei art 'stufen' (Apex — exakt wie vor DL2)
-- Ohne diese Spalte gilt der Standard (Frontend liest liq_regeln mit '*', app.py mit Rückfall ohne die Spalte). Apex einschalten (Finns Entscheid):
--   update public.liq_regeln set dll_schutz = true where firma = 'Apex Trader' and art = 'stufen';
-- Einspielen nur durch den Master (apply_migration). Idempotent. Rückbau: alter table public.liq_regeln drop column dll_schutz;
alter table public.liq_regeln add column if not exists dll_schutz boolean;
comment on column public.liq_regeln.dll_schutz is
  'DL2-Schalter 11.11.2026: true = DL2 am Tageslimit an (Hedge ≥ 100 $ davor, Pflicht-SL, kein WD ohne SL), false = aus, NULL = an bei tagesstart, aus bei stufen (Apex).';

-- Ina (d1f5bcae, pc-xc5c52): heute alle 4 Echo-Starts ausgefallen — Lese-EA in allen 4 Master-Terminals „Snapshot eingefroren“, Copier standby
-- (armed=false). Laut Finn war der PC nachts aus. Finn 16.11.2026 18:4x: „Ja, heute noch“ (nach Hinweis: Planer-Fenster endet 18:30, US-Session).
-- Neue Starts Dubai, ≥ 5 min je ID, Tradeify CFD SELL 122680 vs. BUY 119832 ≥ 60 min. Claim zurück, start_fehler 'neu'. Guard: nichts gesendet.
-- Startet nur, wenn Ina vorher den ProphosHedgeReader in den Master-Terminals neu aufgezogen hat (sonst bricht Echo wieder vor dem Klick ab, nichts gesendet).
update public.trade_plans p
set start_um = v.neu, start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler', coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb)
                   || jsonb_build_object('status','neu','behoben','nachgeholt per SQL 16.11.2026 (Ina PC nachts aus, Lese-EA eingefroren; Finn: heute noch)'))
from (values
  ('a48079ce'::text, timestamptz '2026-11-16 19:12:40+04'),   -- FundingPips 100k 21215751 → P2 SELL
  ('17ad27e6'::text, timestamptz '2026-11-16 19:19:10+04'),   -- FTMO 541478634 → P1 BUY
  ('fae7b661'::text, timestamptz '2026-11-16 19:27:30+04'),   -- Tradeify CFD 100k 122680 → P2 SELL
  ('02d5eca7'::text, timestamptz '2026-11-16 20:31:50+04')    -- Tradeify CFD 100k 119832 → P1 BUY (≥ 60 min nach dem SELL)
) as v(kurz, neu)
where left(p.id::text,8) = v.kurz and left(p.user_id::text,8) = 'd1f5bcae' and p.status='planned' and p.started_at is null and p.orbit_gesendet_at is null;

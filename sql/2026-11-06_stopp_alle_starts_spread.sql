-- STOPP alle Starts bis Finns Wort (Finn 06.11.2026 ~03:40 Dubai: „nicht nur WD, alle Starts allgemein, bis ich mich wieder melde" —
-- Anlass: Fusion-Markets-Spread bei hohem Volumen). Ersetzt die +1-h-Verschiebung aus 2026-11-06_alle_starts_plus_1h_spread.sql.
-- Muster 2026-11-03_hedge_trades_anhalten_bis_fix.sql (alte Startzeit in mt5_baseline.start_vor_stopp) + 2026-10-29_planer_pause.sql.
-- 1. Jeder wartende Plan (planned, nie gestartet, NICHT geclaimt): start_vor_stopp = aktuelle Startzeit, start_um = null → startet nicht.
--    Geclaimte Pläne bleiben unberührt (mitten im Start, sonst Doppelstart).
-- 2. Planer pausiert, damit nichts nachgeplant oder neu terminiert wird: Challenge-Planer, Funded-Planer CFD + Futures, WD-Farmer.
-- Laufende Trades und Hedges bleiben unberührt.
begin;

update public.trade_plans
   set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_vor_stopp', start_um),
       start_um = null, updated_at = now()
 where status = 'planned' and started_at is null and start_um is not null
   and start_um_gestartet_at is null
   and start_um >= now() - interval '5 minutes' and start_um < now() + interval '24 hours';

update public.auto_plan_regeln     set aktiv = false, updated_at = now() where id = 1;
update public.funded_cfd_plan_regeln set aktiv = false, updated_at = now() where id = 1;
update public.funded_plan_regeln   set aktiv = false, updated_at = now() where id = 1;
update public.wd_farmer_regeln     set aktiv = false, updated_at = now() where id = 1;

commit;

-- RÜCKBAU NUR auf Finns Wort („Spread wieder normal"): Planer an, Startzeiten zurück. War die alte Zeit schon vorbei, startet der Plan
-- in 5–25 min gestreut (Jitter-Regel), sonst zur alten Zeit. Abstände der noch kommenden Pläne bleiben so, wie sie waren.
-- begin;
-- update public.trade_plans
--    set start_um = case when (mt5_baseline->>'start_vor_stopp')::timestamptz > now() + interval '5 minutes'
--                        then (mt5_baseline->>'start_vor_stopp')::timestamptz
--                        else now() + make_interval(secs => 300 + floor(random() * 1200)) end,
--        mt5_baseline = mt5_baseline - 'start_vor_stopp', updated_at = now()
--  where status = 'planned' and start_um is null and mt5_baseline ? 'start_vor_stopp';
-- update public.auto_plan_regeln       set aktiv = true, updated_at = now() where id = 1;
-- update public.funded_cfd_plan_regeln set aktiv = true, updated_at = now() where id = 1;
-- update public.funded_plan_regeln     set aktiv = true, updated_at = now() where id = 1;
-- update public.wd_farmer_regeln       set aktiv = true, updated_at = now() where id = 1;
-- commit;

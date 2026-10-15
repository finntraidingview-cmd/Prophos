-- ENDE PULS-PAUSE MIKE + MORITZ (Finn 15.10.2026 ~17:40 Dubai: „Puls ist für IDs deaktiviert … bitte für alle IDs wieder Puls anmachen.
-- Es läuft kein Trade mehr."). Rückweg zu sql/2026-10-14_puls_pause_mike_moritz.sql, angewendet 15.10.2026 13:45 UTC direkt gegen die DB.
-- Zwei Handgriffe:
--   1. Mike (32b854d1…) und Moritz (aff98e60…) zurück in auto_plan_regeln.user_ids → jetzt 8 IDs; der Nachplan-Takt (alle 10 min bis
--      start_bis − 15 min) plant ihre freien Konten für heute, der Nachtlauf wie gewohnt für morgen.
--   2. Die 5 stillgelegten Pläne vom 14.10. (start_um war auf 01.01.2027 geparkt): Startzeit zurück auf start_um_war (14.10.), bleiben
--      unbestätigt. Grund: mit start_um 2027 sah ap_plan_verfallen sie NICHT als tot, und „hat schon einen geplanten/laufenden Plan"
--      hätte ihre 5 Konten im Planer blockiert. Mit der gestrigen Startzeit gelten sie als liegengeblieben: blockieren nicht, starten nie
--      mehr von selbst (sfTick nimmt nur Pläne des eigenen Tages), bleiben als Zeile stehen. Marke puls_pause → puls_pause_ende.
update public.auto_plan_regeln
   set user_ids = user_ids || array['32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid, 'aff98e60-e9a0-4821-9d1d-31634571a2f4'::uuid],
       updated_at = now()
 where id = 1 and not ('32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid = any(user_ids));
update public.trade_plans
   set start_um = (mt5_baseline->'puls_pause'->>'start_um_war')::timestamptz,
       auto_bestaetigt_at = null,
       mt5_baseline = (mt5_baseline - 'puls_pause')
                      || jsonb_build_object('puls_pause_ende', jsonb_build_object('at', now(),
                         'grund', 'Finn 15.10.2026 17:40 Dubai: Puls für alle IDs wieder an; Plan vom 14.10. verfallen, Nachplan-Takt plant neu'))
 where status = 'planned' and mt5_baseline->'puls_pause'->>'at' = '2026-10-14T12:45:00Z';
-- Kontrolle: select user_ids from auto_plan_regeln where id = 1;  → 8 IDs
--            select count(*) from trade_plans where mt5_baseline ? 'puls_pause' and status = 'planned';  → 0

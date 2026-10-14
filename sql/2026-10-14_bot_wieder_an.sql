-- BOT WIEDER AN (14.10.2026 ~23:05 Dubai, Finn: „Ja, Auto-Planer wieder einschalten, Mike und Moritz bleiben in der Puls-Pause")
-- Rückweg zu 2026-10-14_schluss_fuer_heute.sql, damit der Nachtlauf 01:30 Dubai Evals + Handelstage-Minis für morgen plant.
-- Mike/Moritz: weiter nicht in auto_plan_regeln.user_ids, ihre 5 stillgelegten Pläne (Marke puls_pause, start_um 2027) bleiben
-- unberührt — nur die Marke „Schluss für heute" wird entfernt (2 Pläne). Angewendet 14.10.2026 19:05 UTC direkt gegen die DB.
update public.auto_plan_regeln
   set aktiv = true,
       regeln = jsonb_set(regeln, '{ausgleich,aktiv}', 'true'::jsonb),
       updated_at = now()
 where id = 1;
update public.trade_plans
   set mt5_baseline = mt5_baseline - 'puls_pause'
 where status = 'planned'
   and mt5_baseline->'puls_pause'->>'grund' like 'Schluss für heute%';

-- Fusion-Grenze je Login von 60 auf 100 Lot gleichzeitig (Finn 29.10.2026: „nie mehr als 60 Lots gleichzeitig … das würde nicht
-- hinkommen, gut wäre 100 oder so"). Gilt gemeinsam für Echo-Hedge, finalen Tradeify und Apex (ah_param liest max_lots vom Echo-Hedge).
-- Die zweite Grenze — freie Fusion-Marge abzüglich Reserve (eh_marge) — bleibt unverändert und hält weiter, wenn die Marge nicht reicht.
update public.auto_plan_regeln
   set regeln = jsonb_set(jsonb_set(regeln, '{echo_hedge,max_lots}', '100'::jsonb), '{tradeify_final_hedge,max_lots}', '100'::jsonb),
       updated_at = now()
 where id = 1;

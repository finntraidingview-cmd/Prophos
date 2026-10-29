-- Apex-Hedge + Tradeify-Final-Hedge AN (Finn 29.10.2026 ~17:15 Dubai: „Ich will die Trades für Apex und Tradeify … für die jeweiligen
-- bestätigen" — Schalter im Admin waren bei ihm noch nicht sichtbar, Master schaltet per SQL). Wirkung: ah_tick/tfh_tick markieren geplante
-- Apex-Challenges bzw. finale Tradeify-Trades (hedge_art) → Block „Neue Hedge-Trades bestätigen"; ohne hedge_freigabe_at startet keiner
-- (Claim-Riegel a0). Echo-Hedge bleibt AUS. Rücknahme: beide 'false'.
update public.auto_plan_regeln
   set regeln = jsonb_set(jsonb_set(regeln, '{apex_hedge,an}', 'true'::jsonb), '{tradeify_final_hedge,an}', 'true'::jsonb),
       updated_at = now()
 where id = 1;

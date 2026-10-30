-- FUNDED-CFD-PLANER: REFUND-LOTS HALBIEREN (Finn 30.10.2026 14:2x, Anlass EzPoker a1ad322f: „Bei Refund-Trades bitte die Lot Sizes halbieren. Der Take Profit
-- ist ganz klein, da kauft er viel zu viele Lots"). firmen[].erster_payout.lots_faktor = 0.5 bei FundedNext. Ziel in $, SL in $ und Hedge-€ auf DD bleiben, nur
-- die Punkte verdoppeln sich. app.py rechnet ohne den Schlüssel ebenfalls mit 0,5; die Zeile macht ihn sichtbar und änderbar. Gilt nur für neue Vorschläge.
-- Idempotent (jsonb_set überschreibt nur lots_faktor, und nur wo erster_payout ein Objekt ist).
update public.funded_cfd_plan_regeln r
   set firmen = (select coalesce(jsonb_agg(case when f->'namen' ? 'fundednext' and jsonb_typeof(f->'erster_payout') = 'object'
                                                 then jsonb_set(f, '{erster_payout,lots_faktor}', '0.5'::jsonb)
                                                 else f end order by i), '[]'::jsonb)
                   from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
       updated_at = now()
 where r.id = 1;

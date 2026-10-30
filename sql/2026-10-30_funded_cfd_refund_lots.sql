-- FUNDED-CFD-PLANER: REFUND-LOTS ÷ 5 (Finn 30.10.2026 14:49: „Refund-Trades: Lot-Anzahl runter, durch 5.", ersetzt ÷ 2 von 14:2x, Anlass EzPoker a1ad322f).
-- firmen[].erster_payout.lots_faktor = 0.2 bei FundedNext. Ziel in $, SL in $ und Hedge-€ auf DD bleiben, nur die Punkte × 5.
-- app.py rechnet ohne den Schlüssel ebenfalls mit 0,2; die Zeile macht ihn sichtbar und änderbar. Gilt nur für neue Vorschläge.
-- Idempotent (jsonb_set überschreibt nur lots_faktor, und nur wo erster_payout ein Objekt ist).
update public.funded_cfd_plan_regeln r
   set firmen = (select coalesce(jsonb_agg(case when f->'namen' ? 'fundednext' and jsonb_typeof(f->'erster_payout') = 'object'
                                                 then jsonb_set(f, '{erster_payout,lots_faktor}', '0.2'::jsonb)
                                                 else f end order by i), '[]'::jsonb)
                   from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
       updated_at = now()
 where r.id = 1;

-- FUNDED-CFD-PLANER: ERSTER PAYOUT = REFUND (Finn 30.10.2026 ~08:00, nur FundedNext — FTMO folgt, sobald es im Planer ist).
-- Solange ein FundedNext-Funded-Konto noch keinen Payout hatte (pending_payouts + managed_payouts je Konto = 0, dieselbe Zählung wie bei
-- The5ers): Ziel +50 bis +150 $ (TP aufs Ziel, auch nach Verlust ganz — kein TP-Deckel, kein Mindest-TP 250), Hedge hedge_eur_je_dd € je $
-- Drawdown = 0,5 → 100k 5.000 € auf 10.000 $, 50k 2.500 € auf 5.000 $, 200k 10.000 € auf 20.000 $. Ab dem ersten Payout die normalen
-- FundedNext-Regeln. SL/Lots/1-%-Regel unverändert. app.py (fcp_erster_payout) hat denselben Standard; diese Zeile macht ihn sichtbar und
-- änderbar ("erster_payout": false schaltet ihn für die Firma ab). Idempotent (|| überschreibt nur den Schlüssel).
update public.funded_cfd_plan_regeln r
   set firmen = (select coalesce(jsonb_agg(case when f->'namen' ? 'fundednext'
                                                 then f || '{"erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5}}'::jsonb
                                                 else f end order by i), '[]'::jsonb)
                   from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
       updated_at = now()
 where r.id = 1;

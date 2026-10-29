-- FundingPips 2-Step Standard: größere TPs (Finn 30.10.2026 ~02:55 Dubai, nach Prüfung des Help Centers: die „Profit Concentration
-- Policy" — ein Trade > 60 % des Phasenziels → auf dem Master 4 Gewinntage vor jeder Auszahlung — gilt nur für Käufe 27.06.–27.09.2026;
-- alle 13 aktiven HT-FundingPips-Challenges sind ab 28.09. gekauft. Finn: „Phase 1 auf 5000 bis 7000, Phase 2 3500 bis 4000, bei Flex
-- änderst du nichts, nur bei Standard").
-- Werte gelten für 100k, der Planer skaliert nach Größe (50k = halb). Vorher: phase1 tp [3150,3600] tp_max 3600, phase2 tp [1800,2250]
-- tp_max 2250. SL unverändert. Flex (Block flex) unverändert.
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'fundingpips'
                               then jsonb_set(jsonb_set(jsonb_set(jsonb_set(f,
                                      '{phasen,phase1,tp}', '[5000,7000]'::jsonb), '{phasen,phase1,tp_max}', '7000'::jsonb),
                                      '{phasen,phase2,tp}', '[3500,4000]'::jsonb), '{phasen,phase2,tp_max}', '4000'::jsonb)
                               else f end order by ord)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as t(f, ord))),
       updated_at = now()
 where r.id = 1;

-- Die heutigen FundingPips-Vorschläge (alle ungestartet, noch mit den alten TPs) raus — wie der Admin-Knopf „Löschen"; der Nachplan-Takt
-- (alle 10 min) plant die Konten ohne Plan neu, jetzt mit den neuen TPs. Finn bestätigt sie danach neu.
delete from public.trade_plans
 where auto_plan = true and status = 'planned' and master_firm ilike 'fundingpips%'
   and start_um_gestartet_at is null and started_at is null and orbit_gesendet_at is null;

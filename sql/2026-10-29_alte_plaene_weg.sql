-- Vier liegengebliebene Auto-Pläne raus, der Nachtlauf (01:00 Dubai) plant die Konten neu (Finn 29.10.2026 ~00:10 Dubai:
-- „alles weg löschen und morgen neu"). Wie der Admin-Knopf „Löschen" (nur planned, nie gestartete Order). Geprüft vorher:
-- Marco FTMO …4934 hatte um 05:47 einen Start-Fehler (Copier-Panel nicht erreichbar) — Balance 107.395,92 = Plan-Balance,
-- keine Master-Position → es ging keine Order raus.
-- Sicherung der Kernwerte (zum Nachbauen, falls nötig):
--   231ed41e-aa7e-46b7-84cb-50faafaad27b Marco  FTMO 100k 541494934 Phase 1   mt5v2 buy  33 Lot  TP 2654 SL 2180  Start 29.10. 05:47
--   301a14ad-2122-4fd5-b486-74b85b13287a Ina    Apex 100k …0019 Challenge       tvv2  sell 3 NQ   TP 7734           Start 29.10. 17:33 (hedge_art apex)
--   81b6f678-5ae0-415a-943f-428f606057fc Simon  Tradeify 150k …4357 Challenge  tvv2  sell 2 NQ   TP 3480           Start 29.10. 20:04 (Waage-Deckel aufgegeben)
--   880b8b11-0226-430d-9ce6-7675b951314f Marc   Tradeify 150k …7231 Challenge  tvv2  sell 3 NQ   TP 2039           Start 30.10. 16:09 (hedge_art tradeify_final, 10,59 Lot / 675 €)
delete from public.trade_plans
 where status = 'planned' and started_at is null and orbit_gesendet_at is null
   and id in ('231ed41e-aa7e-46b7-84cb-50faafaad27b', '301a14ad-2122-4fd5-b486-74b85b13287a',
              '81b6f678-5ae0-415a-943f-428f606057fc', '880b8b11-0226-430d-9ce6-7675b951314f');

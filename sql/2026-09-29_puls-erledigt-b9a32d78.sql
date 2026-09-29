-- 29.09.2026: „Erledigt = fertig" (Finn: „ich hab den Trade manuell schon erledigt, deswegen soll das ja eigentlich wegfallen").
-- Plan b9a32d78 (150k Apex …0024, CDP-Testtrade, Demo-TP 14:58 UTC, erledigt 15:10 UTC mit der Schätzung 32 $) stand noch in der
-- Balance-Nachlesung um 15:47:49 UTC (Regel F5: erledigte Pläne bis 12 h nachlesen). Der neue Frontend-Stand liest erledigte Pläne
-- nie mehr nach — bis er auf dem PC-Tab angekommen ist, stoppt puls_aufgegeben die Lesung auch im alten Stand (tvV2EndlesungGrund).
-- Einmalige Datenkorrektur, nur dieser Plan, nur solange keine End-Balance gelesen ist.
update trade_plans
set mt5_baseline = jsonb_set(
      mt5_baseline, '{final}',
      (mt5_baseline->'final') || jsonb_build_object(
        'puls_aufgegeben', true,
        'puls_fehler', 'erledigt von Hand — Puls liest nicht mehr nach (Finn 29.09.2026)'))
where id = 'b9a32d78-d07d-4dee-a8f5-7df68bb3efce'
  and status = 'completed'
  and (mt5_baseline->'final'->'balance_end') is null;

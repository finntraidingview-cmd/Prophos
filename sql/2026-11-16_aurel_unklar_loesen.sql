-- Aurel Tradeify 150k TDFYSL150916042926 → Challenge (bd7ba0de, SELL, Start 03:17): start_fehler puls_still mit unklar=true
-- („Geclaimt, danach kein Ergebnis, Tab neu geladen → in TradingView prüfen“). Die Marke sperrte Aurels Tradeify-WD d41d37c3 (Richtungs-Schutz).
-- Finn 16.11.2026 ~18:45 mit TradingView-Screenshot: Positions leer, Equity 154.228,52, Profit 0 → keine Order gelaufen.
-- Wie „⚠ UNKLAR lösen“ auf der Karte: unklar weg, Plan bleibt planned (heute zu spät, der Nachtlauf plant neu).
update public.trade_plans p
set mt5_baseline = jsonb_set(p.mt5_baseline, '{start_fehler}', (p.mt5_baseline->'start_fehler') || jsonb_build_object(
      'unklar', false, 'behoben', 'UNKLAR gelöst per SQL 16.11.2026: TradingView geprüft, keine Position (Finn)'))
where p.id::text like 'bd7ba0de%' and p.status = 'planned' and (p.mt5_baseline->'start_fehler'->>'unklar') = 'true';

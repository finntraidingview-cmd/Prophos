-- Trades pro Tag: Verteilung 1/2/3/4 Trades von 80/12/6/2 auf 65/21/10/4 (Finn 11.11.2026 ~07:20 Dubai: „dass der Ein-Trade zu 65 % ist, und die anderen
-- 2, 3, 4 gegebenenfalls so anpassen“ — Rest 35 % im alten Verhältnis 12:6:2 verteilt, gerundet). Wirkt für IDs, die geteilt werden, aber NICHT im Testmodus:
-- Test-IDs (Marco, Simon) haben test_n = 3 fest. Idempotent.
update auto_plan_regeln
   set regeln = jsonb_set(regeln, '{tagesteilung,anteile}', '[65, 21, 10, 4]'::jsonb), updated_at = now()
 where id = 1 and regeln ? 'tagesteilung';

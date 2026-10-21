-- Auto-Abhaken kurz AN, dann wieder AUS (21.10.2026 ~21:47–21:55 Dubai). Finn wollte „Trades ohne Hedge, bei denen nichts passiert ist, automatisch
-- abhaken". Der Schalter abhaken_auto (sql/2026-10-19_abhaken_auto_schalter.sql) schaltet aber auch den Blow-Takt: um 21:48–21:49 wurden
-- 11 geblowte Pläne abgehakt + Konto archiviert (Finn will Geblowt sehen). Sofort wieder aus. Getrennte Schalter folgen
-- (sql/2026-10-21_abhaken_auto_getrennt.sql, Code app.py).
update auto_plan_regeln set regeln = coalesce(regeln, '{}'::jsonb) || '{"abhaken_auto": true}'::jsonb where id = 1;   -- 21:47 ausgeführt
update auto_plan_regeln set regeln = regeln - 'abhaken_auto' where id = 1;                                              -- 21:55 ausgeführt

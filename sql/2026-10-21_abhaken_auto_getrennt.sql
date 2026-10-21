-- Auto-Abhaken: zwei getrennte Schalter (Finn 21.10.2026 ~21:55 Dubai: „Automatisch abhaken nur, wenn ein normaler Orbit- oder normaler
-- Echo-Trade ohne Gegenhedge gelaufen ist und NICHTS passiert ist. Sehen will ich weiter: geblowt, bestanden, Rest/Take-Profit-Fälle,
-- bei denen ich entscheide, ob es zum Planer geht.“). Anlass: regeln.abhaken_auto = true schaltete auch den Blow-Takt — der hakte um
-- 21:48 Dubai 11 geblowte Pläne ab und archivierte sie still.
--
-- Ab dem app.py-Stand mit ap_auto_abhaken_schalter_lesen (erst nach dem Railway-Deploy wirksam):
--   regeln.abhaken_auto_normal = true  → Normal-Takt (ap_normal_auto_tick): nur Orbit V2 / Echo V2 ohne Hedge, Challenge/Phase 1/2,
--                                        echte Lesung, über dem Boden, Rest bis Ziel ≥ 500 $, Ende am TP oder SL (nie Schließen-Knopf,
--                                        Auto-Close, Liquidation, Tage-Mini), kein Konto weg, kein Ziel-Tag, kein Balance-Sprung,
--                                        kein manuell/Review
--   regeln.abhaken_auto_blow   = true  → Blow-Takt (ap_blow_auto_tick): geblowt abhaken + archivieren — Standard AUS
--   regeln.abhaken_auto        = true  → alter Schalter, schaltet aus Sicherheit NUR noch den Normal-Takt, nie mehr den Blow-Takt
-- Fehlt ein Schlüssel = AUS. Review-weiter (Konto schon weitergestellt/archiviert) läuft immer.
--
-- NICHT vor dem Railway-Deploy ausführen (auf dem alten Stand schaltet nur abhaken_auto, dann wieder beide Takte).

-- Normal-Takt an, alter Schalter weg, Blow-Takt ausdrücklich aus:
update auto_plan_regeln
   set regeln = (coalesce(regeln, '{}'::jsonb) - 'abhaken_auto') || '{"abhaken_auto_normal": true, "abhaken_auto_blow": false}'::jsonb
 where id = 1;

-- Prüfen:
--   select regeln->'abhaken_auto_normal' as normal, regeln->'abhaken_auto_blow' as blow, regeln->'abhaken_auto' as alt
--     from auto_plan_regeln where id = 1;
-- Normal-Takt wieder aus:
--   update auto_plan_regeln set regeln = regeln || '{"abhaken_auto_normal": false}'::jsonb where id = 1;
-- Blow-Takt an (nur wenn Finn es ausdrücklich will):
--   update auto_plan_regeln set regeln = regeln || '{"abhaken_auto_blow": true}'::jsonb where id = 1;

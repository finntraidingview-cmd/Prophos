-- 15.10.2026 (Finn): kein Opening-/Nachmittags-Anteil mehr („50 % da und da ist mittlerweile ganz egal, es ist immer Volumen da") —
-- EIN Fenster für alle Trades: 02:00–18:00 Dubai, gleichmäßig über den Tag gewürfelt, letzter Start 18:00 Dubai (vorher 18:30).
-- zeiten liegt in deutscher Zeit (zeiten.tz = Europe/Berlin): 00:00–16:00 dt = 02:00–18:00 Dubai, solange Sommerzeit gilt;
-- ab 25.10.2026 (Winterzeit, Abstand 3 h) wären das 03:00–19:00 Dubai — dann 23:00–15:00 dt setzen, falls Finn bei 02:00–18:00 Dubai bleibt.
-- Vorher: fenster [["00:00","14:30",50],["14:30","16:30",50]], start_bis "16:30".
update auto_plan_regeln
   set zeiten = coalesce(zeiten, '{}'::jsonb)
                || jsonb_build_object('fenster', jsonb_build_array(jsonb_build_array('00:00', '16:00', 100)),
                                      'start_bis', '16:00')
 where id = 1;

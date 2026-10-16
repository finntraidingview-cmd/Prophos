-- NEUE KONTEN SOFORT (Finn 16.10.2026): Zeitfenster Planen + Starten für Challenge-Typen (challenge/phase1/phase2):
--   Futures 02:00–20:00 Dubai, CFD 02:15–18:00 Dubai — gilt auch für neu angelegte Konten und Nachfolger aus „Überprüfen".
-- Futures DST-fest in Dubai-Zeit (Master/Finn: „Finn denkt in Dubai-Zeit"): zeiten.fenster_tz = Asia/Dubai, fenster 02:00–20:00 (Gewicht 100
-- wie bisher), start_bis 20:00 — app.py rechnet je Tag in deutsche Minuten um (ap_fenster_liste / ap_start_bis; vorher fest 00:00–18:00 dt,
-- ab 25.10. wären das 03:00–21:00 Dubai gewesen). Ohne fenster_tz gelten fenster/start_bis weiter als deutsche Zeit.
-- CFD: zeiten.cfd_ab = 02:15 Dubai (Finn: „CFDs erst ab 02:15" bleibt; bisher Code-Standard 00:20 dt = 02:20 Dubai) und neu zeiten.cfd_bis
-- = 18:00 Dubai — app.py rechnet beide je Tag in deutsche Minuten um (ap_zeit_dt_min, Sommer-/Winterzeit von selbst).
-- ERST NACH DEM PUSH des Codes einspielen: alter Code läse fenster/start_bis als deutsche Zeit (02:00–20:00 dt = 04:00–22:00 Dubai).
-- Die 16-Uhr-Regel neuer Konten (zeiten.neu_bis, sql/2026-10-15_nachplan_neu_bis.sql) ist durch diese Fenster ersetzt — der Code liest sie
-- seit .15xx nicht mehr; der Schlüssel wird hier entfernt, damit niemand ihn für wirksam hält. Wiederholbar.
update auto_plan_regeln
   set zeiten = (coalesce(zeiten, '{}'::jsonb) - 'neu_bis')
                || jsonb_build_object('fenster_tz', 'Asia/Dubai',
                                      'fenster', jsonb_build_array(jsonb_build_array('02:00', '20:00', 100)),
                                      'start_bis', '20:00',
                                      'cfd_ab', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '02:15'),
                                      'cfd_bis', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '18:00'))
 where id = 1;

-- Prüfen:
-- select zeiten->>'fenster_tz' as fenster_tz, zeiten->'cfd_ab' as cfd_ab, zeiten->'cfd_bis' as cfd_bis, zeiten ? 'neu_bis' as neu_bis_noch_da, zeiten->'fenster' as fenster, zeiten->>'start_bis' as start_bis
--   from auto_plan_regeln where id = 1;

-- 15.10.2026 (Finn, Faustregel): heute neu angelegte Konten (Neukauf / Nachfolger aus „Überprüfen") plant der Nachplan-Takt nur noch für
-- heute ein, wenn sie VOR 16:00 Dubai angelegt wurden — sonst erst der Nachtlauf für den nächsten Handelstag (app.py ap_konto_neu_zu_spaet).
-- Die Grenze steht ausdrücklich in zeiten.neu_bis; ohne den Schlüssel gilt derselbe Standard im Code (AP_NEU_BIS_STANDARD).
update auto_plan_regeln
   set zeiten = coalesce(zeiten, '{}'::jsonb) || jsonb_build_object('neu_bis', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '16:00'))
 where id = 1;

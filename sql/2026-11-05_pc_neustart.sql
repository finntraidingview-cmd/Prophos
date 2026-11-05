-- TÄGLICHER NEUSTART JE PC (DR1, Finn 05.11.2026: „Wenn man das komplette Backend und auch die Prophos-Seite daily einmal neu startet, dann
-- müsste ja der RAM in der Cache gelöscht werden.“). Einstellung in der bestehenden Regel-Zeile puls_heim_regel (id 1), Railway liest sie mit
-- „select *“ (60 s Cache) und meldet dem Panel im Tab-Stand, ob der PC jetzt neu starten darf (app.py pc_neustart_sicht).
--   an                  false = aus (Standard bis zum Test)
--   tz / von / bis      Fenster, Standard 02:30–05:00 Dubai; im Fenster startet das Panel im ersten ruhigen Moment, gestreut 1–20 min
--   nur_pcs             [] = alle PCs, sonst nur diese Kennungen (Testlauf: ein PC)
--   ruhe_vor_start_min  so lange vor einem Start (Handplan / bestätigter Vorschlag) kein Neustart, Standard 30
--   teile               DR1b: {"backend": true, "reader": true} — lokales Backend (Port 5000) / Reader (8790) mit neu starten; nur false schaltet ab
-- Fehlt die Spalte (Datei nicht eingespielt), ist der Neustart aus — nichts bricht.
-- NICHT von Slave 5 eingespielt.

alter table public.puls_heim_regel
  add column if not exists pc_neustart jsonb not null
  default '{"an": false, "tz": "Asia/Dubai", "von": "02:30", "bis": "05:00", "nur_pcs": [], "ruhe_vor_start_min": 30, "teile": {"backend": true, "reader": true}}'::jsonb;

-- Testlauf (erst nach dem Push mit panel.py/copier.py/app.py, auf Finns Wort): nur ein PC, z. B. PC von Emin
-- update public.puls_heim_regel set pc_neustart = pc_neustart || '{"an": true, "nur_pcs": ["pc-onkrbk"]}'::jsonb where id = 1;
-- Wieder aus:
-- update public.puls_heim_regel set pc_neustart = pc_neustart || '{"an": false}'::jsonb where id = 1;
-- Ergebnis je PC (Panel → Tab → mt5_live.status.panel_lauf.tages_neustart):
-- select pc_name, status->'panel_lauf'->'tages_neustart' from public.mt5_live where pc_name = 'pc-onkrbk' order by updated_at desc limit 1;

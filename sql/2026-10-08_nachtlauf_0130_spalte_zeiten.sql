-- 2026-10-08 — Nachtlauf 01:30 Dubai in die SPALTE auto_plan_regeln.zeiten (Fund Slave 1, Gegenprüfung 08.10.2026 21:15 Dubai).
-- Finn 07.10.2026 05:30 Dubai: „mach das auf 1 Uhr 30 Dubai nachts". sql/2026-10-07_auto_plan_nachtlauf_0130.sql schrieb den Wert aber
-- nach regeln.zeiten — app.py ap_nacht_tick liest die Spalte zeiten (select zeiten → ap_nacht_param). Folge: der Nachtlauf blieb auf
-- dem Code-Standard AP_NACHT_STANDARD 01:00 Dubai (Auto-Pläne vom 07.10. alle um 21:00 UTC entstanden).
-- Hier: nachtlauf in die Spalte zeiten mischen (übrige Schlüssel bleiben), den wirkungslosen Eintrag aus regeln.zeiten entfernen.
-- ap_nacht_tick liest die Parameter alle 10 min neu — kein Railway-Neustart nötig. Wiederholbar.
-- Rückbau: update auto_plan_regeln set zeiten = zeiten - 'nachtlauf' where id = 1;   (→ wieder 01:00 Dubai)
update public.auto_plan_regeln
   set zeiten = coalesce(zeiten, '{}'::jsonb) || '{"nachtlauf": {"uhr": "01:30", "tz": "Asia/Dubai"}}'::jsonb,
       regeln = case when jsonb_typeof(regeln->'zeiten') = 'object'
                     then jsonb_set(regeln, '{zeiten}', (regeln->'zeiten') - 'nachtlauf') else regeln end,
       updated_at = now()
 where id = 1;
-- Kontrolle: select zeiten->'nachtlauf', regeln->'zeiten' from auto_plan_regeln where id = 1;

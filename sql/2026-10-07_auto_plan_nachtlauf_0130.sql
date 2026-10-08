-- 2026-10-07 — Nachtlauf des Auto-Planers auf 01:30 Dubai (Finn 07.10.2026 05:30 Dubai: „mach das auf 1 Uhr 30 Dubai nachts").
-- Vorher: kein Eintrag → Code-Standard AP_NACHT_STANDARD 01:00 Asia/Dubai (app.py ap_nacht_param). Parameter
-- auto_plan_regeln.regeln.zeiten.nachtlauf {uhr, tz}; zeiten bleibt sonst wie es ist (war bisher null → Standards im Code).
-- Eingespielt 07.10.2026 05:35 Dubai (Master). Wiederholbar.
update auto_plan_regeln
   set regeln = jsonb_set(regeln, '{zeiten}',
                coalesce(regeln->'zeiten', '{}'::jsonb) || '{"nachtlauf": {"uhr": "01:30", "tz": "Asia/Dubai"}}'::jsonb),
       updated_at = now()
 where id = 1;
-- Kontrolle: select regeln->'zeiten'->'nachtlauf' from auto_plan_regeln where id = 1;

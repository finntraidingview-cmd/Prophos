-- Finn 05.11.2026 ~07:00 Dubai: „FundedNext Futures bei Emin auf einfach Orbit Prio 2“ (statt Orbit V2).
-- MO1c (05.11.2026, Master/Finn): Emins Gruppe plant FundedNext Futures (50k-Challenges Amir …6923/…6243, Emin …3807/…9183/…2748), HT NICHT
-- (HT-Regel fundednextfutures bleibt planen=false, die 15 HT-150k-FNF-Challenges von Finn + Pascal bleiben aus). Modell: Standard Orbit V2, bis Finn es ändert.
-- Eine Quelle: auto_plan_gruppe.firmen_modell (Spalte aus sql/2026-11-05_orbit_prio2.sql) — ein Modell-Eintrag schaltet die Firma für die Gruppe an
-- (app.py ap_gruppe_firma_an). Gleiches geht nach dem Deploy auch in Einstellungen → Challenge-Planer → Futures → FundedNext Futures → „Modell · Gruppe Emin“.
-- NICHT automatisch einspielen. Rückbau: update … set firmen_modell = firmen_modell - 'fundednextfutures' where gruppe_id = '90c616f3-…';
update public.auto_plan_gruppe
   set firmen_modell = coalesce(firmen_modell, '{}'::jsonb) || '{"fundednextfutures": "orbit_prio2"}'::jsonb,
       updated_at = now()
 where gruppe_id = '90c616f3-3ec1-49cb-b3ba-8a267d0a43df';

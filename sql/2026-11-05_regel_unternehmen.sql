-- REGEL JE UNTERNEHMEN = STANDARD + ABWEICHUNG JE FELD (Phase 1 Challenge-Planer, Finn 05.11.2026 ~06:35 über den Master) — NICHT automatisch einspielen.
-- Standard = auto_plan_regeln id=1 (heute bearbeitet HT genau diese Regel). Ein Unternehmen (Verwalter-Gruppe) speichert in auto_plan_gruppe.regeln NUR
-- seine Abweichungen: {"firmen": {namen[0]: {Pfad…: Wert}}, "zeiten": {"fenster": […]}} — wirksame Regel = Standard überlagert mit den Abweichungen
-- (app.py ap_unt_regeln/ap_reg_unternehmen); nicht Geändertes folgt dem Standard live. Leer = alles Standard (bitgleich wie bisher).
-- Phase 1 änderbar: Firma an/aus + Modell (firmen_modell, MO1b/c), TP, Kontrakte, Puffer, Schritt, Startfenster. Ziel/Drawdown/Boden folgen in Phase 2.
-- Rückbau: alter table public.auto_plan_gruppe drop column regeln;
alter table public.auto_plan_gruppe add column if not exists regeln jsonb not null default '{}'::jsonb;

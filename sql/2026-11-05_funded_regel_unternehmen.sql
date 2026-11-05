-- UNT4: FUNDED-PLANER-REGELN JE UNTERNEHMEN = STANDARD + ABWEICHUNG JE FELD (Master 05.11.2026) — NICHT automatisch einspielen.
-- Standard = funded_plan_regeln id 1 (Futures) bzw. funded_cfd_plan_regeln id 1 (CFD) = HT. Ein Unternehmen (Verwalter-Gruppe, auto_plan_gruppe)
-- speichert NUR seine Abweichungen: funded_regeln = {"futures": {"firmen": {namen[0]: {Pfad…: Wert}}},
--                                                    "cfd": {"firmen": {namen[0]: {…}}, "parameter": {k: v}}}
-- Wirksame Regel = Standard + Abweichung (app.py fd_unt_reg); nicht Geändertes folgt dem Standard live. Leer = alles Standard (bitgleich).
-- Änderbar: jedes Firmen-Feld, das es im Standard gibt (an, Werte je Größe, Lock, Consistency, Refund …) und die CFD-Parameter;
-- Schalter, Zeiten/Startfenster, Abstände, Grenzen (konst) und News-Regel gelten für alle. Stempel regeln_at (sql/2026-11-05_regel_unternehmen.sql).
-- Ohne diese Spalte läuft alles als Standard; Speichern einer Abweichung antwortet „Einstellungen je Unternehmen noch nicht freigeschaltet".
-- Rückbau: alter table public.auto_plan_gruppe drop column funded_regeln;
alter table public.auto_plan_gruppe add column if not exists funded_regeln jsonb not null default '{}'::jsonb;

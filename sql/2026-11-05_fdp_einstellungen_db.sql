-- 2026-11-05 — Einstellungen Funded Planer → Futures: Grenzen aus dem Code in die DB (E2b-Nachtrag, Finn 05.11.2026 ~03:55 Dubai: „Nimm dir Winning Days
-- als Beispiel: Da kann ich die Uhrzeit ändern, das Verhältnis ändern, die Lots ändern, alles … So soll es bei den anderen Planern auch sein“).
--
-- Neue Spalte funded_plan_regeln.konst (jsonb). LEER = jeder Wert fällt auf die Konstante in app.py zurück (fdp_konst) — nach dem Einspielen plant der
-- Planer also genau wie vorher. Geändert wird erst über Funded Planer → Futures → Einstellungen → „Grenzen“ (POST /admin/funded-plan/regeln, nur Admin,
-- „Finn + Pascal“, „Pascal“). Schlüssel (Konstante, Grenzen): breakeven_tol (500, 0–5000 $), sl_min (100, 1–5000 $), tages_puffer (100, 1–1000 $),
-- liq_puffer (50, 1–1000 $), liq_min (300, 0–10000 $), bestaetigen_vorlauf_min (2, 1–60 min), bestaetigen_streu_min (10, 1–60 min).
-- Das eigene Startfenster braucht KEIN SQL: es steht in der bestehenden Spalte zeiten (zeiten.fenster_eigen {von, bis, tz}); ohne den Schlüssel gilt wie
-- bisher das Fenster des Challenge-Planers.
-- Ohne diese Spalte zeigt der Reiter die Grenzen mit dem Hinweis „SQL einspielen“, Speichern dort wird abgelehnt; alles andere läuft.
-- Ausführen nur auf Finns Wort (Master), nicht von einem Slave. Rückbau: alter table public.funded_plan_regeln drop column konst;

alter table public.funded_plan_regeln add column if not exists konst jsonb not null default '{}'::jsonb;

-- Kontrolle (soll {} zeigen):
-- select id, konst, zeiten from public.funded_plan_regeln where id = 1;

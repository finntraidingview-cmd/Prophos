-- 2026-11-05: Zufall-Parameter des Challenge-Planers in auto_plan_regeln.regeln.zufall (Auftrag E3b, S6).
-- Finn 05.11.2026 ~03:45 Dubai: „Dann die Parameter, die fürs Zufallsprinzip genommen werden, sodass ich die bearbeiten kann — wie bei Winning Days."
--
-- Bisher standen diese Werte nur im Code (app.py). Seit E3b liest der Planer regeln.zufall je Schlüssel (ap_zufall). Fehlt ein Schlüssel oder ist er
-- ungültig, gilt einzeln der Code-Wert. Diese Datei trägt GENAU die Code-Werte ein. Gleiche Zahlen → gleiche Pläne (Selbsttest
-- tools/selftest_einstellungen_challenge.py, Teil 4). Ohne diese Datei läuft alles wie bisher; die Einstellungen zeigen die Werte dann als „Code".
--
--   paar_extern_min    [2, 5]   AP_PAAR_ABSTAND_EXTERN  Futures-Paar über zwei Firmen: der spätere startet 2–5 min nach dem Anker
--   paar_intern_min    [2, 30]  AP_PAAR_ABSTAND         Futures-Paar in derselben Firma (zwei IDs): 2–30 min
--   paar_pc_min        3        AP_PAAR_PC_MIN          derselbe PC: kein anderer Start in ± 3 min
--   paar_rs_min        30       AP_PAAR_RS_MIN          Richtungsschutz beim Rücken: keine Gegenrichtung derselben ID × Firma in ± 30 min
--   verteil_jitter_min 8        AP_VERTEIL_JITTER_MIN   Streuung hinter dem frühesten freien Platz beim Verteilen
--   fenster_wuerfe     20       AP_FENSTER_WUERFE       so oft würfelt der Planer die Plätze im Zeitfenster, der fenster-treueste gewinnt
--   gegen_wuerfe       16       AP_GEGEN_WUERFE         so oft würfelt der Planer Zeiten + Richtungen neu, der beste Lauf gilt
--
-- Idempotent: schon vorhandene Schlüssel in regeln.zufall bleiben (die Standardwerte stehen links vom ||, der Bestand rechts gewinnt).
-- Ausführen nur auf Finns Wort (Master), nicht von einem Slave.

-- ── 1. Vorschau (nur lesen) ──
select id, regeln->'zufall' as zufall_vorher, updated_at from auto_plan_regeln where id = 1;

-- ── 2. Eintragen ──
update auto_plan_regeln
set regeln = jsonb_set(
      coalesce(regeln, '{}'::jsonb), '{zufall}',
      '{"paar_extern_min": [2, 5], "paar_intern_min": [2, 30], "paar_pc_min": 3, "paar_rs_min": 30,
        "verteil_jitter_min": 8, "fenster_wuerfe": 20, "gegen_wuerfe": 16}'::jsonb
      || coalesce(case when jsonb_typeof(regeln->'zufall') = 'object' then regeln->'zufall' end, '{}'::jsonb),
      true),
    updated_at = now()
where id = 1
  and not (coalesce(case when jsonb_typeof(regeln->'zufall') = 'object' then regeln->'zufall' end, '{}'::jsonb)
           ?& array['paar_extern_min', 'paar_intern_min', 'paar_pc_min', 'paar_rs_min', 'verteil_jitter_min', 'fenster_wuerfe', 'gegen_wuerfe']);

-- ── 3. Kontrolle ──
select id, regeln->'zufall' as zufall_nachher, updated_at from auto_plan_regeln where id = 1;

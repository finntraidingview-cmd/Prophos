-- FE1b Funded-Planer Futures (funded_plan_regeln id 1): Tagesdeckel je ID aus + Ziel-Toleranz 10 % (Finn 11.11.2026 20:45 Dubai, Code live seit .2194).
-- Finn: „Tagesdeckel bei beiden nicht machen, wir haben die Regel, dass nie mehr als zwei Orbit-Trades gleichzeitig laufen“
--   → zeiten.max_je_id_tag = 0 (0 = kein Tagesdeckel je ID, app.py fdp_planen/fdp_auswahl). Die Zwei-Orbit-Regel (Puls-Heim) bleibt.
-- Finn: „Mach die Range plus 10 % Toleranz“ / „Wenn ein Account bei Tradeify auf 12.000 geht, ist er auch durch“
--   → je_groesse.<Größe>.ziel_toleranz_pct = 10: erreicht ab Untergrenze des Ziel-Gewinns × 0,9 (app.py fdp_ziel_schwelle).
-- Nur diese Felder, sonst nichts. Idempotent (setzt immer 0 bzw. 10). Unternehmens-Abweichungen (Emin, ap_unt_kontext) bleiben unberührt (Zwei Unternehmen getrennt).
-- Stand id 1 beim Schreiben (lesend geprüft): max_je_id_tag 3. Ziel-Spannen: FTMO Futures 50k [4.000–4.500] → ab 3.600 · Lucid 150k, Topstep 150k,
-- Tradeify 150k [13.000–19.000] → ab 11.700. Apex 100k/150k haben KEINE Spanne, sondern feste Ziele 12.000 / 15.000 → mit 10 % ab 10.800 / 13.500 (Teil 3, eigener
-- Block — weglassen, falls Finns „Range plus 10 %“ Apex nicht meint). FundedNext Futures hat keine Größen → nichts.

-- 1) Tagesdeckel je ID aus
update funded_plan_regeln set zeiten = coalesce(zeiten, '{}'::jsonb) || '{"max_je_id_tag": 0}'::jsonb, updated_at = now()
where id = 1 and coalesce(zeiten->>'max_je_id_tag', '') <> '0';

-- 2) Ziel-Toleranz 10 % für jede Größe mit Ziel-SPANNE [von, bis] (Tradeify, Lucid, Topstep, FTMO Futures)
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when jsonb_typeof(f->'je_groesse') = 'object' then
      jsonb_set(f, '{je_groesse}', (select coalesce(jsonb_object_agg(g.key, case when jsonb_typeof(g.value->'ziel_gewinn') = 'array'
                                                                       then g.value || '{"ziel_toleranz_pct": 10}'::jsonb else g.value end)
                                    , '{}'::jsonb) from jsonb_each(f->'je_groesse') g))   -- coalesce: leeres je_groesse ergäbe NULL → Eintrag weg
      else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and exists (select 1 from jsonb_array_elements(r.firmen) f, jsonb_each(coalesce(f->'je_groesse', '{}'::jsonb)) g
                           where jsonb_typeof(g.value->'ziel_gewinn') = 'array' and coalesce(g.value->>'ziel_toleranz_pct', '') <> '10');

-- 3) Apex (festes Ziel als Zahl, keine Spanne): ebenfalls 10 % — nur einspielen, wenn Finns „plus 10 % Toleranz“ auch Apex meint
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'apex' and jsonb_typeof(f->'je_groesse') = 'object' then
      jsonb_set(f, '{je_groesse}', (select coalesce(jsonb_object_agg(g.key, case when jsonb_typeof(g.value->'ziel_gewinn') = 'number'
                                                                       then g.value || '{"ziel_toleranz_pct": 10}'::jsonb else g.value end)
                                    , '{}'::jsonb) from jsonb_each(f->'je_groesse') g))   -- coalesce: leeres je_groesse ergäbe NULL → Eintrag weg
      else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and exists (select 1 from jsonb_array_elements(r.firmen) f, jsonb_each(coalesce(f->'je_groesse', '{}'::jsonb)) g
                           where f->'namen' ? 'apex' and jsonb_typeof(g.value->'ziel_gewinn') = 'number' and coalesce(g.value->>'ziel_toleranz_pct', '') <> '10');

-- Kontrolle
-- select r.zeiten->>'max_je_id_tag' deckel, f->>'name' firma, g.key groesse, g.value->'ziel_gewinn' ziel, g.value->>'ziel_toleranz_pct' tol
-- from funded_plan_regeln r, jsonb_array_elements(r.firmen) f, jsonb_each(coalesce(f->'je_groesse','{}'::jsonb)) g where r.id = 1 order by 2, 3;

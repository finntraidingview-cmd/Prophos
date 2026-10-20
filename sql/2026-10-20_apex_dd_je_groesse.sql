-- APEX KERNWERTE JE KONTOGRÖSSE (Finn 20.10.2026 16:40 Dubai: „Wenn ein Account unter dem Maximum Loss liegt, muss er als geblowt gelten —
-- nicht nur 100k → 97k, sondern alle Größen, so wie bei Apex die Regeln sind: 150k und 250k genauso"). Apex-Tabelle (Evaluation und PA gleich,
-- Trailing-Schwelle vom Start): 25k → 1.500 · 50k → 2.500 · 75k → 2.750 · 100k → 3.000 · 150k → 4.000 (Finn 17:35: „ja hast recht, ist 4k Drawdown“) · 250k → 6.500 · 300k → 7.500
-- (Boden = Größe − DD: 23.500 / 47.500 / 72.250 / 97.000 / 146.000 / 243.500 / 292.500). Gilt für Evaluation und PA/Funded.
-- Trägt NUR je_groesse.dd_usd (alle sieben Größen) in auto_plan_regeln.regeln.firmen[apex] nach — `groessen` bleibt [100000, 150000]
-- (Prüfer S2 20.10.2026: min(groessen) ist die Bezugsgröße des Vorrat-Startwerts, app.py ~8158, und die Nachkauf-Größenwahl; mit 25k
-- darin rechnete der Vorrat für Apex mit 25k statt 100k). Folge: für 25k/50k/75k/250k/300k gilt der Boden im Radar (Größe aus dem Namen),
-- der Erledigt-Klick/Planer kennt diese Größen erst, wenn Finn sie in `groessen` aufnimmt — heute gibt es nur 100k und 150k. EINE Quelle für Planer, Radar-Boden und Erledigt-Klick
-- (ap_kw_param.dd_je_groesse; ohne DB-Eintrag gilt APEX_DD_JE_GROESSE_USD in app.py als Rückfall). Bestehende je_groesse-Blöcke (100k mit
-- Phasen) bleiben erhalten, nur dd_usd/daily_usd werden je Größe gesetzt bzw. ergänzt. NICHT automatisch eingespielt — Finn/Master.
-- Dieselben Werte wie AP_APEX_DD_JE_GROESSE_USD in app.py (Rückfall ohne DB-Eintrag).
-- Wiederholbar.
update auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
     select jsonb_agg(
       case when exists (select 1 from jsonb_array_elements_text(coalesce(f->'namen', '[]'::jsonb)) n where lower(n) like '%apex%')
            then f
                 || jsonb_build_object('je_groesse',
                      coalesce(f->'je_groesse', '{}'::jsonb)
                      || jsonb_build_object(
                           '25000',  coalesce(f->'je_groesse'->'25000',  '{}'::jsonb) || '{"dd_usd": 1500}'::jsonb,
                           '50000',  coalesce(f->'je_groesse'->'50000',  '{}'::jsonb) || '{"dd_usd": 2500}'::jsonb,
                           '75000',  coalesce(f->'je_groesse'->'75000',  '{}'::jsonb) || '{"dd_usd": 2750}'::jsonb,
                           '100000', coalesce(f->'je_groesse'->'100000', '{}'::jsonb) || '{"dd_usd": 3000}'::jsonb,
                           '150000', coalesce(f->'je_groesse'->'150000', '{}'::jsonb) || '{"dd_usd": 4000}'::jsonb,
                           '250000', coalesce(f->'je_groesse'->'250000', '{}'::jsonb) || '{"dd_usd": 6500}'::jsonb,
                           '300000', coalesce(f->'je_groesse'->'300000', '{}'::jsonb) || '{"dd_usd": 7500}'::jsonb))
            else f end
       order by o)
     from jsonb_array_elements(regeln->'firmen') with ordinality as t(f, o)))
 where id = 1;

-- Kontrolle:
-- select f->'groessen', f->'je_groesse' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f::text ilike '%apex%';

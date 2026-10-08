-- TOPSTEP-KETTE einschalten (08.10.2026, Finn mit Slave-Terminal 3 — Konzept als Baum bestätigt): je Topstep-Konto und Tag zwei Trades
-- statt einem ohne SL. Trade 1 00:00–11:00 dt, SL/TP je zufällig 1.950–2.650 $, 3–4 NQ; Trade 2 legt app.py (ap_kette_tick) an, sobald
-- Puls die Balance nach Trade 1 genau nachgelesen hat: TP2 = 4.500 − E1, SL2 = 4.700 + E1, Start 11:00–19:30 dt, Richtung frei ohne
-- Gegenhedge über IDs, Bestätigung von Trade 1 geerbt. Der Block "kette" an der Topstep-Regel schaltet das ein; fehlende Felder nimmt
-- app.py aus AP_KETTE_STANDARD. Wiederholbar (überschreibt den Block). Nur auf Finns Go einspielen.
-- Rückbau: dieselbe Abfrage mit  f - 'kette'  statt  f || jsonb_build_object(...)
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'topstep'
                               then f || jsonb_build_object('kette', jsonb_build_object(
                                      't1_bis', '11:00', 't1_sl', jsonb_build_array(1950, 2650), 't1_tp', jsonb_build_array(1950, 2650),
                                      't2_ab', '11:00', 't2_bis', '19:30', 'tagesziel_usd', 4500, 'blow_puffer_usd', 200,
                                      'menge', jsonb_build_array(3, 4), 'puffer', jsonb_build_array(25, 40),
                                      't2_abstand_min', jsonb_build_array(5, 20), 't2_streuung_min', jsonb_build_array(0, 45)))
                               else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as e(f, o))),
       updated_at = now()
 where id = 1;
-- NIE ZWEIMAL TRADE 2 (Prüfer Slave 2, 08.10.2026): beim Railway-Deploy laufen alter und neuer Container einige Sekunden parallel, jeder
-- mit eigenem ap_loop — fällt die genaue Lesung von Trade 1 genau dahin, legten beide Trade 2 an. Partial-Unique-Index auf kette.vor;
-- app.py nimmt den 409 als „schon da". Rückbau: drop index if exists public.trade_plans_kette_vor_uniq;
create unique index if not exists trade_plans_kette_vor_uniq on public.trade_plans ((mt5_baseline -> 'kette' ->> 'vor'))
  where mt5_baseline -> 'kette' ->> 'vor' is not null;
-- Prüfen: select f->'kette' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'topstep';

-- NP2b (Slave 5, 05.11.2026 ~17:55 Dubai): FundedNext Futures 50k …26243 (Konto 8e8289ed) im Gruppen-Nachplanen wieder freigeben.
-- Befund: Nach dem Einspielen von sql/2026-11-05_emin_futures_neu_planen.sql hat der Nachplan-Takt um 17:47 Dubai die fünf anderen Konten
-- neu geplant (Orbit Prio 2, Hedge-Vorschau 1,93 / 1,66 ×3 / 1,16). …26243 blieb draußen: im Gruppen-Protokoll auto_plan_gruppe.letzter_lauf
-- steht für heute noch die alte Zeile „keine Regel für diese Firma" (aus einem Lauf VOR firmen_modell.fundednextfutures = orbit_prio2).
-- Das ist ein Regel-Grund (AP_NACHPLAN_FEST_GRUENDE / AP_NACHPLAN_REGEL_GRUENDE) und gilt für den Takt als fest, bis die Gruppen-Regel
-- NACH dem Lauf geändert wurde (ap_gruppe_regel_bezug: auto_plan_regeln.updated_at, auto_plan_gruppe.regeln_at — Spalte live noch nicht da,
-- sql/2026-11-05_regel_unternehmen.sql —, Prozess-Merker). Der Nachplan-Lauf 17:47 hat letzter_lauf.at neu gesetzt und die Zeile beim
-- Mischen behalten (ap_gruppe_lauf_mischen: Zeilen nicht nachgerechneter Konten bleiben) → heute kein Neurechnen mehr. Die Regel stimmt
-- aber längst: …16923 (gleiche Firma, gleiche ID) wurde im selben Takt geplant.
-- Was diese Datei tut: nur diese eine ausgelassen-Zeile aus dem Protokoll der Gruppe entfernen. Der nächste 5-min-Takt (bis 19:45 Dubai)
-- sieht das Konto dann als Kandidat und plant es wie …16923. Ohne die Datei plant es der Nachtlauf 01:30 Dubai für morgen (voller Lauf,
-- kennt keine festen Gründe) — sie holt nur den heutigen Tag. Keine Pläne, keine Konten, kein HT berührt. Wiederholbar: ohne die Zeile
-- trifft das update nichts.
-- NICHT von Slave 5 eingespielt.

update public.auto_plan_gruppe
   set letzter_lauf = jsonb_set(letzter_lauf, '{ausgelassen}',
                                coalesce((select jsonb_agg(z) from jsonb_array_elements(letzter_lauf->'ausgelassen') z
                                           where z->>'konto_id' is distinct from '8e8289ed-233a-4aa3-bcb7-e12307a6c420'), '[]'::jsonb))
 where gruppe_id = '90c616f3-3ec1-49cb-b3ba-8a267d0a43df'
   and letzter_lauf->>'tag' = to_char(now() at time zone 'Europe/Berlin', 'YYYY-MM-DD')
   and letzter_lauf->'ausgelassen' @> '[{"konto_id": "8e8289ed-233a-4aa3-bcb7-e12307a6c420", "grund": "keine Regel für diese Firma"}]'::jsonb;

-- Kontrolle: Zeile weg, ~5 min später ein Plan für …26243 (route tvv2, mt5_baseline.hedge_art apex)
-- select exists(select 1 from jsonb_array_elements(letzter_lauf->'ausgelassen') z where z->>'konto_id' = '8e8289ed-233a-4aa3-bcb7-e12307a6c420') noch_drin
--   from public.auto_plan_gruppe where gruppe_id = '90c616f3-3ec1-49cb-b3ba-8a267d0a43df';
-- select left(id::text,8), status, route, mt5_baseline->>'hedge_art', mt5_baseline->'hedge_vorschau'->>'lots', start_um at time zone 'Asia/Dubai'
--   from public.trade_plans where master_account_id = '8e8289ed-233a-4aa3-bcb7-e12307a6c420' and status in ('planned','open');

-- FF2 „PUMP IN 2 TRADES“ IM FUNDED-PLANER FUTURES (Finn 11.11.2026 ~01:50–02:33 Dubai: „Hochpumpen in einem einzigen Tag … zu 70 % ein einziger Trade, zu 30 % zwei
-- Trades“; Lucid „eins zu eins die gleiche Logik, nur bei Lucid halt Daily Drawdown … von 2,7k“). Konstrukt FINAL + Schnittstelle: side-session-notes
-- 2026-11-11_FF2_tradeify_pump_konstrukt.md / 2026-11-11_FF2_schnittstelle_backend.md. Frontend: Commit 3e5bb12d (E2_P2 in prophos.html).
--
-- REIHENFOLGE: ERST den Backend-Code pushen (fdp_* kennt tp_modus 'pump2', fdp_regeln_aendern nimmt die neuen Schlüssel an, Selbsttest
-- tools/selftest_ff2_pump.py grün), DANN diese Datei einspielen. Der alte Code würde tp_modus 'pump2' als „normal“ lesen (keine Stufen bei Tradeify/Lucid →
-- „keine Stufe“, kein Plan) — harmlos, aber die Karte zeigte schon das aktive Modell, ohne dass etwas plant. NICHT vom Slave eingespielt.
--
-- Was die Datei tut (idempotent, zweimal einspielen ändert nichts):
--   1. funded_plan_regeln.firmen: Eintrag Tradeify → tp_modus 'pump2', je_groesse 150000 mit den Standardwerten des Konstrukts, an = false.
--   2. funded_plan_regeln.firmen: Eintrag Lucid Trading → dieselbe Logik mit daily_usd 2.700, SL 2.600–2.700, sl_hinter_liq false, hedge_eur null (Finn hat
--      keinen Satz genannt — Frontend und Backend lassen das Modell ohne Hedge nicht einschalten), an = false.
--   3. liq_regeln: Lucid Trading funded 150k Daily Loss 2.700 ab Tagesstart (weich, Tagespause, Konto lebt) — bisher nur für challenge (sql/2026-11-05_liq_lucid_daily.sql).
--      maxdd_art eod_trailing + Lock 100 wie id 12 (LH1, sql/2026-11-10_lucid_mll_lock_100.sql) mitgetragen: liq_regel_waehlen nimmt nur die spezifischste Zeile,
--      ohne die beiden Felder fiele der EOD-Boden mit Lock weg. WIRKUNG auch heute schon: Radar/Liq der laufenden Lucid-150k-Fundeds zeigen das Daily weich (2.700 ab
--      Tagesstart), Blow weiter nur am Max Loss. Vor dem Einspielen die Kontrolle unten an den Master geben (fehlt die Zeile wirklich? Gibt es eine allgemeine funded-Zeile?).
-- Einschalten (an = true) nur auf Finns Wort, in der Karte Funded-Planer → Futures → Einstellungen.
-- DB-LESUNG 11.11.2026 (Master): funded_plan_regeln id 1 Tradeify [tradeify] und Lucid Trading [lucidtrading, lucid] je an=false, tp_modus null, je_groesse null →
-- der erste Lauf überschreibt nur leere Einträge. liq_regeln Lucid: id 12 (kontotyp null) eod_trailing Lock +100, id 14 winning_days, id 15/16 challenge 150k 2.700 / 50k 1.200 —
-- funded fehlt wirklich → Abschnitt 3. Nur 150k: für 50k Funded gibt es keinen Beleg (firm_rules.json kennt Lucid nicht), und HT hat Lucid-Fundeds nur in 150k.
-- Erster Lauf ersetzt je_groesse und setzt an = false: laut Seed (sql/2026-10-27_funded_planer.sql) tragen Tradeify und Lucid heute nur {name, namen, an: false} —
-- vor dem Einspielen mit der zweiten Kontrollabfrage unten bestätigen. Danach greift die not-exists-Wache (tp_modus pump2) und nichts wird mehr überschrieben.

-- 1) Tradeify 150k
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'tradeify' then
      (f - 'je_groesse') || jsonb_build_object(
        'name', 'Tradeify', 'namen', jsonb_build_array('tradeify'), 'an', false, 'symbol', 'NQ', 'lock_usd', 100, 'tp_modus', 'pump2',
        'je_groesse', jsonb_build_object('150000', jsonb_build_object(
          'ziel_gewinn', jsonb_build_array(13000, 19000), 'dd', 4500, 'hedge_eur', 850, 'hedge_auf_usd', 4500, 'pump2_pct', 30,
          'ein_kontrakte', jsonb_build_object('3', 1), 'ein_sl', jsonb_build_array(4500, 4700),
          't1_von', '03:00', 't1_bis', '16:00', 't1_tp', jsonb_build_array(4000, 8000), 't1_kontrakte', jsonb_build_object('2', 0.5, '3', 0.5), 't1_sl', jsonb_build_array(4500, 4700),
          'sl_kein_pct', 50, 'sl_hinter_liq', true,
          't2_bis', '18:30', 't2_abstand_min', jsonb_build_array(2, 5), 't2_min_fenster_min', 10, 't2_kontrakte', jsonb_build_object('3', 1), 't2_sl_be_pct', 50)))
    else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and r.firmen @> '[{"namen": ["tradeify"]}]'
  and not exists (select 1 from jsonb_array_elements(r.firmen) f where f->'namen' ? 'tradeify' and f->>'tp_modus' = 'pump2');   -- schon gesetzt: Finns Änderungen bleiben

-- 2) Lucid Trading 150k (Daily Loss 2.700, Hedge offen)
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'lucid' then
      (f - 'je_groesse') || jsonb_build_object(
        'name', 'Lucid Trading', 'namen', jsonb_build_array('lucidtrading', 'lucid'), 'an', false, 'symbol', 'NQ', 'lock_usd', 100, 'tp_modus', 'pump2',
        'je_groesse', jsonb_build_object('150000', jsonb_build_object(
          'ziel_gewinn', jsonb_build_array(13000, 19000), 'dd', 4500, 'daily_usd', 2700, 'hedge_eur', null, 'hedge_auf_usd', 4500, 'pump2_pct', 30,
          'ein_kontrakte', jsonb_build_object('3', 1), 'ein_sl', jsonb_build_array(2600, 2700),
          't1_von', '03:00', 't1_bis', '16:00', 't1_tp', jsonb_build_array(4000, 8000), 't1_kontrakte', jsonb_build_object('2', 0.5, '3', 0.5), 't1_sl', jsonb_build_array(2600, 2700),
          'sl_kein_pct', 50, 'sl_hinter_liq', false,
          't2_bis', '18:30', 't2_abstand_min', jsonb_build_array(2, 5), 't2_min_fenster_min', 10, 't2_kontrakte', jsonb_build_object('3', 1), 't2_sl_be_pct', 50)))
    else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and r.firmen @> '[{"namen": ["lucid"]}]'
  and not exists (select 1 from jsonb_array_elements(r.firmen) f where f->'namen' ? 'lucid' and f->>'tp_modus' = 'pump2');

-- 3) liq_regeln: Lucid funded 150k Daily Loss weich ab Tagesstart
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'Lucid Trading', 'funded', 150000, 'tagesstart', 2700, 'eod_trailing', 100,
       'Lucid 150k Funded: Daily Loss 2.700 $ ab Tagesstart = Tagespause, Konto lebt; Blow nur am Max Loss 4.500 EOD, Lock Größe + 100 (wie id 12 / LH1).',
       'Finn 11.11.2026 (FF2: „bei Lucid halt Daily Drawdown … von 2,7k“, über den Master)'
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'funded' and groesse = 150000);

-- Kontrolle (vor dem Einspielen an den Master):
--   select id, firma, kontotyp, groesse, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd from liq_regeln where firma ilike '%lucid%' order by id;
--   select f->>'name', f->>'tp_modus', f->'an', f->'je_groesse' from funded_plan_regeln, jsonb_array_elements(firmen) f where id = 1 and (f->'namen' ? 'tradeify' or f->'namen' ? 'lucid');

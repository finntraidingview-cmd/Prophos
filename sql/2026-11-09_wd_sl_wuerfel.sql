-- WD-SL-WÜRFEL (WS1, Finn 09.11.2026 abends „bau das Ganze“; Anlass: Rally zur Eröffnung, 4 Winning Days zerbröselt): der WD-Planer würfelt
-- JE WD-TRADE, ob und wie weit ein Stop Loss sitzt — 50 % kein SL · 10 % SL 10–20 % des Puffers · 10 % 20–30 % · 30 % 30–40 %; innerhalb der Spanne
-- zufällig. Puffer = Balance vor dem Trade − Liq-Balance (dieselbe Liq wie der WD-Weg: liq_regeln/Konto-Boden/Größe + 100, app.py hf_wd_master_verlust),
-- NICHT fester Max DD. Beispiel Tradeify 150k: Balance 165.000, Liq 150.100 → Puffer 14.900 → 1.490–2.980 / 2.980–4.470 / 4.470–5.960 $.
-- Schnittstelle: side-session-notes …/WS1_schnittstelle.md.
--
-- Neue Spalte wd_farmer_regeln.sl_wuerfel (jsonb), Zeile id 1:
--   {"an": bool, "stufen": [{"anteil": 0–100, "von": 0–100 | null, "bis": 0–100 | null}, …]}
--   von/bis null = Stufe „kein SL“; Anteile zusammen 100. Eigene Spalte statt vorplan.regeln: wdHedgeSpeichern baut vorplan beim Speichern neu
--   und ließe fremde Schlüssel fallen (wie firmen_regeln / zyklus_regel).
-- Gelesen von: app.py _wd_sl_wuerfel_lesen (Spalte fehlt / null / an=false → aus = wie bisher kein SL; kaputte Anteile → Standard aus dem Code
-- WD_SL_WUERFEL_STD), geschrieben von prophos.html Funded-Planer → Winning Days → Einstellungen (WS1b). Schreiben wie die übrigen Spalten der
-- Tabelle über deren RLS (Policy „wd_farmer_regeln angemeldet“, sql/2026-09-22_wd_farmer.sql) — keine eigenen Rechte nötig.
-- Ergebnis am Plan: trade_plans.master_sl (SL in $, nur wenn gewürfelt) + mt5_baseline.wd_sl {ohne, stufe, pct, usd, puffer, balance, liq_balance, regel}.
-- REIHENFOLGE: egal (Code liest mit Rückfall „aus“). Mit dem Einspielen ist der Würfel AN (Standardwert unten). Wiederholbar.
-- Rückbau: update public.wd_farmer_regeln set sl_wuerfel = jsonb_set(sl_wuerfel, '{an}', 'false') where id = 1;  (ganz: alter table … drop column sl_wuerfel)
--   Ausschalten IMMER über an=false, nie per null: null heißt zwar auch „aus“, ein erneutes Einspielen dieser Datei setzt null aber wieder auf den Standard (an).
-- NICHT vom Slave eingespielt.

alter table public.wd_farmer_regeln add column if not exists sl_wuerfel jsonb;

update public.wd_farmer_regeln
   set sl_wuerfel = jsonb_build_object(
         'an', true,
         'stufen', jsonb_build_array(
           jsonb_build_object('anteil', 50, 'von', null, 'bis', null),   -- kein SL
           jsonb_build_object('anteil', 10, 'von', 10,   'bis', 20),
           jsonb_build_object('anteil', 10, 'von', 20,   'bis', 30),
           jsonb_build_object('anteil', 30, 'von', 30,   'bis', 40)))
 where id = 1 and sl_wuerfel is null;

comment on column public.wd_farmer_regeln.sl_wuerfel is
  'WS1 09.11.2026: Zufalls-SL je WD-Trade {an, stufen [{anteil, von, bis}]} in % des Puffers (Balance vor dem Trade − Liq-Balance); von/bis null = kein SL; NULL/an=false = aus';

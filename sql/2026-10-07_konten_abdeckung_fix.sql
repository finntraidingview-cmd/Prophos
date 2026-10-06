-- EINGESPIELT 07.10.2026 03:20 Dubai (Master): Block 1 (1 Zeile) und Block 2 (2 Zeilen) sind live. Block 5 entschieden:
-- FundingPips-Konten mit 12.000 bleiben (alter Flex-Plan), die Regel 10 % gilt für neue Konten — kein SQL. Block 3/4 bleiben offen (Doku).
-- 2026-10-07 — Konten-Abdeckung Auto-Planer: Datenfixes (Terminal 2, Auftrag KONTEN-ABDECKUNG-DATEN, Master 07.10.2026)
-- NUR VORBEREITET. Der Master spielt ein, nachdem Finn die Punkte bestätigt hat. Jeder Block einzeln ausführbar und
-- idempotent (Bedingungen im where). Keine Namen oder Kontonummern (Repo ist öffentlich), nur IDs.
--
-- Befund Nachtlauf 07.10.2026 00:12 dt (auto_plan_lauf 19): über die drei Planer-IDs gibt es 17 nicht archivierte
-- Challenge-/Phase-Konten, 12 geplant, 5 ausgelassen. Die anderen aktiven Konten sind funded / funded_cfd / winning_days /
-- Fusion und liegen per Bauart (AP_TYPEN) außerhalb des Auto-Planers. Ausgelassen: 2 × The5%ers (alte Vorschläge, Block 2),
-- 1 × FundedNext Futures ohne Balance (Block 3), 2 × Blue Guardian ohne Regel (Block 4).

-- 1) Apex-Challenge-Konto mit max_drawdown 400 statt 4.000 (Tippfehler; Apex 150k = 4.000 $ Drawdown). Das Konto liegt bei
--    einer ID außerhalb des Planers, aber Radar-Liq-Level und master_risk eines Plans lesen accounts.max_drawdown, sobald die
--    Firmen-Regel keinen Wert liefert (ap_konto_rechnen: Apex-Phase ohne dd_usd → risiko None → accounts.max_drawdown).
update accounts
   set max_drawdown = 4000, updated_at = now()
 where id = 'a3aeda67-b6eb-4f64-acc7-ab2350be44a3'
   and max_drawdown = 400;

-- 2) Zwei Auto-Vorschläge The5%ers vom 05.10. 23:12 dt (planned_for 06.10., Start 16:55 / 16:56 dt): nie bestätigt, nie
--    gestartet (started_at null, kein Order-Signal), aber am 06.10. 21:28 dt vom PC-Tab „geclaimt" (start_um_gestartet_at
--    gesetzt). Damit zählen sie in ap_planen nicht mehr als Vorschlag (_vorschlag prüft start_um_gestartet_at) und blockieren
--    beide Konten jede Nacht mit „hat schon einen geplanten/laufenden Plan". Löschen → der nächste Lauf plant die Konten neu.
--    Code-Hinweis an den Master: der Claim darf unbestätigte Auto-Vorschläge nicht als „gestartet" markieren (oder _vorschlag
--    muss start_um_gestartet_at ohne started_at ignorieren), sonst wiederholt sich das bei jedem verpassten Vorschlag.
delete from trade_plans
 where id in ('0a530c7a-a734-4d11-a497-b898bc3fe32e', 'de5ac8ca-b89a-4c2f-9a68-228fb8cf8c83')
   and auto_plan = true
   and status = 'planned'
   and started_at is null
   and auto_bestaetigt_at is null;

-- 3) KEIN SQL — FundedNext-Futures-Challenge 78247db3-… hat keine Balance (tv_balance leer, nie gelesen, keine MetaApi).
--    acc_balance_wahl nimmt bewusst keine Handbalance → einmal „↻" bzw. Puls-Lesung am PC, dann plant der Nachtlauf das Konto.

-- 4) KEIN SQL OHNE FINN — Blue Guardian fehlt in auto_plan_regeln.regeln.firmen; zwei 100k-Phase-1-Konten werden jede Nacht mit
--    „keine Regel für diese Firma" ausgelassen (Konten tragen max_drawdown 8.000 = 8 %). Vorlage, Platzhalter ? = Finns Werte
--    (Ziel je Phase, Kaufpreis, TP/SL-Spannen in $, Lots NAS100 mit 10 $/Pkt je Lot):
-- update auto_plan_regeln
--    set regeln = jsonb_set(regeln, '{firmen}', (regeln->'firmen') || jsonb_build_array(jsonb_build_object(
--          'namen', jsonb_build_array('blueguardian'), 'route', 'mt5v2', 'boden', 'statisch', 'dd_pct', 8,
--          'groessen', jsonb_build_array(100000), 'kauf_eur', ?, 'ziel_pct', jsonb_build_object('phase1', ?, 'phase2', ?),
--          'phasen', jsonb_build_object(
--             'phase1', jsonb_build_object('sl', jsonb_build_array(?, ?), 'tp', jsonb_build_array(?, ?), 'menge', jsonb_build_array(?, ?),
--                                          'puffer', jsonb_build_array(50, 75), 'ziel_pct', ?, 'boden_pct', 8, 'menge_schritt', 0.1),
--             'phase2', jsonb_build_object('sl', jsonb_build_array(?, ?), 'tp', jsonb_build_array(?, ?), 'menge', jsonb_build_array(?, ?),
--                                          'puffer', jsonb_build_array(50, 75), 'ziel_pct', ?, 'boden_pct', 8, 'menge_schritt', 0.1))))),
--        updated_at = now()
--  where id = 1
--    and not exists (select 1 from jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'blueguardian');

-- 5) FRAGE, KEIN SQL — FundingPips-Konten tragen max_drawdown 12.000 (Phase 1 bei einer Planer-ID, Funded bei einer anderen),
--    die Planer-Regel rechnet dd_pct 10 (= 10.000 auf 100k) und die Funded-Hedge-Vorgabe im Frontend mit 12.000. Welcher Wert gilt?

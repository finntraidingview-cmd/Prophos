-- 2026-11-09 — WS2 „Trades pro Tag aufteilen“ (Finn 09.11.2026 abends, Konstrukt WS2 abgesegnet; Anlass: die Eröffnungs-Rally hat alle offenen Shorts
-- erwischt — „Aktuell ist es immer 1 Trade pro Tag, und dann ist es ein Pump, und dann ist der Account durch“).
--
-- Legt den Einstellungs-Block auto_plan_regeln.regeln.tagesteilung an (id 1 = HT-Standard), NUR wenn er fehlt (idempotent, überschreibt nie Finns Werte).
-- an = false: nach dem Einspielen plant der Planer genau wie vorher (1 Trade je Konto und Tag). Eingeschaltet wird über Challenge-Planer → Einstellungen
-- (WS2b, POST /admin/auto-plan/ablaufwert {tagesteilung: {an: true}}). Leser in app.py: tt_param — jedes Feld einzeln, Ungültiges fällt auf den Code-Standard.
--
-- Felder: an · firmen (regeln.firmen[].namen[0]; FTMO-/FundedNext-Futures bewusst nicht, per Häkchen zuschaltbar; Apex nie) · anteile 1/2/3/4 Trades in % ·
-- haupt_pct (Anteil des Haupt-Trades am Tagesziel) · neben_pkt (TP-Abstand Neben-Trades, NQ-/Index-Punkte) · neben_sl_faktor (Neben-SL = Faktor × TP-Abstand) ·
-- neben_menge_max (höchstens dieser Anteil der Haupt-Lots) · min_tp_usd (kleinere Teile werden zusammengelegt) · abstand_min (Pause nach der genauen Lesung) ·
-- schluss_pct / schluss_min (Zufalls-Schluss WS2c) · gruppen (id_gruppen.id der Unternehmen, die zusätzlich zu HT teilen; leer = nur HT) ·
-- nur_konten (leer = alle; sonst NUR diese Konto-IDs — Testbetrieb, Werte nie im Repo) · test_n (null | 1–4: feste Anzahl für nur_konten) ·
-- schluss_topstep (Zufalls-Schluss auch bei Topstep, Standard aus) · schluss_news_sperre (kein Zufalls-Schluss rund um News, Standard an) — beide kopiert der
-- Planer in mt5_baseline.zschluss (WS2c entscheidet am Plan).
-- Ausführen nur auf Finns Wort (Master). Rückbau: update auto_plan_regeln set regeln = regeln - 'tagesteilung' where id = 1;

update public.auto_plan_regeln
   set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{tagesteilung}', jsonb_build_object(
         'an', false,
         'firmen', jsonb_build_array('tradeify', 'lucidtrading', 'topstep', 'fundednext', 'fundingpips', 'the5ers', 'ftmo', 'blueguardian', 'tradeifycfd'),
         'anteile', jsonb_build_array(80, 12, 6, 2),
         'haupt_pct', jsonb_build_array(70, 90),
         'neben_pkt', jsonb_build_array(10, 25),
         'neben_sl_faktor', jsonb_build_array(1, 2),
         'neben_menge_max', 0.5,
         'min_tp_usd', 300,
         'abstand_min', jsonb_build_array(1, 180),
         'schluss_pct', jsonb_build_array(5, 10),
         'schluss_min', jsonb_build_array(2, 120),
         'gruppen', jsonb_build_array(),
         'nur_konten', jsonb_build_array(),
         'test_n', null,
         'schluss_topstep', false,
         'schluss_news_sperre', true), true),
       updated_at = now()
 where id = 1
   and not (coalesce(regeln, '{}'::jsonb) ? 'tagesteilung');

-- Kontrolle (soll den Block mit an = false zeigen):
-- select regeln->'tagesteilung' from public.auto_plan_regeln where id = 1;

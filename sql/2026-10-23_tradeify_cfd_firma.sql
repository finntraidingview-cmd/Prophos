-- Tradeify CFD als neue CFD-Firma (Finn 23.10.2026: 100k 2-Step, MT5 „TradeifyVenturesFX-Server", Name in Prophos
-- „Tradeify CFD"). Werte aus Finns Screenshots: NAS100 Kontraktgröße 10 (= 10 $/Pkt je Lot, Lots 0,01–50), Ziel Phase 1 5 %
-- (105.000), Phase 2 10 % (110.000) — bei dieser Firma bewusst umgekehrt —, Max Loss 10.000 $ statisch (Boden 90.000), Tageslimit
-- 3.000 $, keine Mindesttage, keine Consistency, Kauf 340 €, Split 80 % (Split steht im Frontend admPayoutPctDefault, nicht hier).
-- Planer-Werte von Finn (23.10.2026): P1 TP 3.500–4.500 / SL 2.000–2.500, P2 TP 6.000–7.500 / SL 2.000–2.500. Lots ohne eigene
-- Erfahrung aus Blue Guardian abgeleitet (gleicher Punktwert 10 $/Pkt, 27 Trades 20 Tage: Ø 4 Lots, SL ~69 Pkt, TP ~122 Pkt) →
-- SL 2.000–2.500 $ bei ~70 Pkt = 2,8–3,6 Lots.
-- Eingespielt 23.10.2026 ~12:50 Dubai auf Finns Wort („Schablone live schalten, damit ich es nutzen kann") VOR dem Umbau der
-- Tradeify-Erkennung (Slave 4). Darum planen:false — der Auto-Planer plant Tradeify CFD noch nicht ein (nur Kernwerte), bis der Umbau
-- live ist; sonst gilt das Konto an ~25 Stellen als Tradeify-Futures (TradingView-Weg, 90 % Split). Danach:
--   sql/2026-10-23_tradeify_cfd_planen_an.sql. Idempotent.

-- 1) firm_specs je Nutzer (wie Blue Guardian 2026-10-04) — ohne Zeile fällt firmToPreset() ins Futures-Preset
insert into firm_specs (user_id, name, symbol, unit, ppl, currency, dup_symbol, server)
select u.user_id, 'Tradeify CFD', 'NAS100', 'Lots', 10, '$', 'NAS100', 'TradeifyVenturesFX-Server'
from (select distinct user_id from firm_specs) u
where not exists (select 1 from firm_specs f where f.user_id = u.user_id and f.name = 'Tradeify CFD');

-- 2) Auto-Planer-Regel, eigener Schlüssel „tradeifycfd" (ap_regel_finden vergleicht exakt nach _ap_norm)
update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (r.regeln->'firmen') || jsonb_build_array('{
      "namen": ["tradeifycfd"], "route": "mt5v2", "planen": false,
      "boden": "statisch", "dd_pct": 10, "daily_usd": 3000,
      "groessen": [100000], "wert_groessen": [100000], "kauf_eur": {"100000": 340},
      "ziel_pct": {"phase1": 5, "phase2": 10},
      "phasen": {
        "phase1": {"sl": [2000, 2500], "tp": [3500, 4500], "menge": [2.8, 3.6], "menge_schritt": 0.1, "puffer": [75, 100], "ziel_pct": 5, "boden_pct": 10},
        "phase2": {"sl": [2000, 2500], "tp": [6000, 7500], "menge": [2.8, 3.6], "menge_schritt": 0.1, "puffer": [75, 100], "ziel_pct": 10, "boden_pct": 10}
      }}'::jsonb)),
    updated_at = now()
where not exists (select 1 from jsonb_array_elements(r.regeln->'firmen') x where x->'namen' ? 'tradeifycfd');

-- 3) Konto-Schablone (Bulk-Vorlage) wie FTMO/The5%ers: Verlust/Trade = Tageslimit, Profit/Trade = Phase-1-Ziel.
--    Keine Phase-2-Vorlage — Phase 2 entsteht per Phasenwechsel (wie FTMO 2026-10-17).
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, sortierung, aktiv, wd_farm)
select 'Tradeify CFD 100k Phase 1', 'Tradeify CFD', 'phase1', 100000, 100000, 340, 10000,
  3000, 3000, 5000, '100k Tradeify CFD {ex}', 'MT5', 51, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Tradeify CFD 100k Phase 1');

-- BG1 Teil C (Finn 19.11.2026 über den Master: „Den bestehenden einfach Standard geben, auch für die Vorlage, und jetzt noch das Nano hinzufügen.“):
-- zwei zentrale Bulk-Vorlagen Blue Guardian 100k Phase 1 (bisher gab es keine). Werte aus dem Help Center (Bericht .claude/master/berichte/
-- 2026-11-19_BG1_blue_guardian_nano.md) und wie die bestehenden Standard-Konten (Kauf 300 €, Phase 1 mit trading_days 3).
--   Standard: Max DD 8.000 (8 % statisch), Daily 4.000 (4 %) → Loss/Trade 4.000 (= Daily wie bei den anderen Vorlagen), Profit/Trade 8.000 (Ziel P1 8 %),
--             Mindesttage 3 (Blue Guardian zählt Tage mit ≥ 0,5 % Gewinn; bulk_vorlagen hat kein goal_min_profit → trading_days wie die bestehenden P1-Konten).
--   Nano:     Kauf 145 € (167 $), Max DD 10.000 = DIE NANO-KENNUNG (ap_konto_flex, ab_dd_pct 10 in sql/2026-11-19_bg1_blue_guardian_nano.sql),
--             Daily 3.000 (3 %) → Loss/Trade 3.000, Profit/Trade 8.000, KEINE Mindesttage (goal_kind leer).
-- Zwei Schablonen gleicher Firma × Typ × Größe: der Reset wählt seit BG1 Teil C die mit dem Max DD der alten Zeile (konto_vorlage_finden dd=);
-- ein Konto ohne Max DD über /admin/konto-anlegen bekommt die erste = Standard (Sortierung 52 vor 53) — „Standard ist der Normalfall“.
-- name_template wie die anderen Vorlagen; seit .1472 ohne Wirkung (Name baut kontoNameRegel: „100k <External ID> → Phase 1“).
-- Idempotent (insert … where not exists by name). Nicht einspielen ohne Finns Wort (Master).
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, purchase_ccy, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, goal_kind, goal_target, name_template, plattform, sortierung, aktiv, wd_farm)
select 'Blue Guardian 100k Standard Phase 1', 'Blue Guardian', 'phase1', 100000, 100000, 300, 'EUR', 8000,
  4000, 4000, 8000, 'trading_days', 3, '100k Blue Guardian {ex}', 'MT5', 52, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Blue Guardian 100k Standard Phase 1');

insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, purchase_ccy, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, goal_kind, goal_target, name_template, plattform, sortierung, aktiv, wd_farm)
select 'Blue Guardian 100k Nano Phase 1', 'Blue Guardian', 'phase1', 100000, 100000, 145, 'EUR', 10000,
  3000, 3000, 8000, null, null, '100k Blue Guardian {ex}', 'MT5', 53, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Blue Guardian 100k Nano Phase 1');

-- Prüfen (nur lesen):
-- select name, purchase_cost, max_drawdown, max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, goal_kind, goal_target, sortierung
--   from bulk_vorlagen where firm = 'Blue Guardian' order by sortierung;

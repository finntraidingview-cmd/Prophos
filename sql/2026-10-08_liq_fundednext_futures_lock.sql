-- 2026-10-08: liq_regeln — FundedNext Futures: Konto-Boden EOD-trailing mit Lock bei Größe + 100 (Master-Auftrag, Finn 08.10.2026).
-- Finn: „Bei FundedNext Futures ist das maximale Drawdown immer 4.000, bis das Drawdown bei 150.000 stoppt und nicht mehr nachgezogen
-- wird. Erreiche ich z. B. 154.500, ist mein Drawdown für den nächsten Tag 4.500. Bei 156.000 habe ich 6.000. Das rechnet ihr gerade falsch."
-- Beleg (FundedNext-Dashboard, Futures Flex $150K Challenge, Tradovate, Konto …0045): Max loss limit 6.165,44 $, Leiste 150.100 bis
-- 156.265,44 → der Boden steht bei 150.100 (Dashboard gilt vor Finns „150.000"), Höchststand 156.265,44.
--
-- Befund: Die Zeile stand live noch auf maxdd_art 'statisch' (Annahme vom 30.09.2026) — sql/2026-10-05_liq_regeln_fundednext_futures.sql
-- (eod_trailing, Lock 0) wurde nie eingespielt. Statisch = Größe − DD = 146.000 → Radar „Liq −10,3k $" bei Balance 156.265,44
-- (156.265,44 − 146.000 = 10.265,44). Diese Datei ERSETZT die vom 05.10. (Lock 100 statt 0 laut Dashboard).
--
-- Regel (die Rechnung gibt es schon: app.py liq_konto_boden eod_trailing + liq_peak, kein Code geändert):
--   Boden = Höchststand − Max DD, höchstens Größe + 100 (Lock).
--   Höchststand = höchste belegte Balance derselben Phase vor dem Trade: final.balance_end / tv.balance_start früherer Orbit-/Topstep-V2-
--   Pläne des Kontos, die Start-Balance dieses Trades und eine vorher gelesene accounts.tv_balance (liq_peak). Eine Balance-Historie je
--   Tag gibt es nicht — bei einem Trade je Konto und Tag ist das Ende des Trades die Tagesschluss-Balance. Mehrere Trades an einem Tag:
--   ein Zwischenhoch zählt mit (Boden eher zu hoch = vorsichtig).
--   Max DD aus accounts.max_drawdown (aktive FN-Futures-Konten: 4.000), sonst maxdd_usd 4.000.
--   150.000 → 146.000 (4.000) · 153.000 → 149.000 (4.000) · 154.000 → 150.000 (4.000) · 154.500 → 150.100 (4.400)
--   156.000 → 150.100 (5.900) · 156.265,44 → 150.100 (6.165,44 = Dashboard)
-- Nur Anzeige (Radar, Läuft, „geblowt"-Erkennung): Fusion-Hedge-Level (wd_sl_zeile, hedge.sl_level_nq, Hedge-Open) und der Auto-Planer
-- (auto_plan_regeln Kernwerte) lesen liq_regeln nicht. Selbsttest: tools/selftest_liq_regeln.py, Abschnitt 10.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

update public.liq_regeln
   set maxdd_art = 'eod_trailing',
       maxdd_usd = 4000,
       maxdd_lock_ueber_groesse_usd = 100,
       notiz = 'Finn 08.10.2026 (Futures Flex 150K Challenge, Dashboard: Max loss limit 6.165,44 $ von 150.100 bis 156.265,44): '
            || 'EOD-Trailing-Drawdown 4.000 $ — Boden = Höchststand − 4.000, steigt nie über Größe + 100 (150k: ab 154.100 fest '
            || 'bei 150.100). Ersetzt statisch (30.09.) und die nie eingespielte Fassung mit Lock 0 (05.10.). maxdd_usd nur Rückfall '
            || 'ohne accounts.max_drawdown. Keine eigene Liq-Regel — nur Konto-Boden.',
       quelle = 'Finn 08.10.2026 (Screenshot FundedNext-Dashboard Futures Flex $150K Challenge, über den Master)'
 where lower(firma) = 'fundednext futures';

-- Falls die Zeile fehlt: anlegen. Einmalig, nicht doppelt.
insert into public.liq_regeln (firma, kontotyp, art, maxdd_art, maxdd_usd, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'FundedNext Futures', null, null, 'eod_trailing', 4000, 100,
       'Finn 08.10.2026 (Futures Flex 150K Challenge, Dashboard: Max loss limit 6.165,44 $ von 150.100 bis 156.265,44): '
       || 'EOD-Trailing-Drawdown 4.000 $ — Boden = Höchststand − 4.000, steigt nie über Größe + 100 (150k: ab 154.100 fest bei 150.100). '
       || 'maxdd_usd nur Rückfall ohne accounts.max_drawdown. Keine eigene Liq-Regel — nur Konto-Boden.',
       'Finn 08.10.2026 (Screenshot FundedNext-Dashboard Futures Flex $150K Challenge, über den Master)'
 where not exists (select 1 from public.liq_regeln where lower(firma) = 'fundednext futures');

-- Prüfen:
-- select id, firma, kontotyp, art, maxdd_art, maxdd_usd, maxdd_lock_ueber_groesse_usd, left(notiz, 80), quelle
--   from public.liq_regeln where lower(firma) = 'fundednext futures';

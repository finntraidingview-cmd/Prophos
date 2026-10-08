-- ÜBERHOLT (08.10.2026): nie eingespielt; ersetzt durch sql/2026-10-08_liq_fundednext_futures_lock.sql (Lock 100 laut Dashboard). NICHT ausführen.
-- 2026-10-05: liq_regeln — FundedNext Futures: Konto-Boden EOD-trailing statt statisch (Master-Auftrag LIQ-FNF).
-- Anlass (Finn 05.10.2026, Screenshot FundedNext „Futures Flex 150K Challenge": Profit target 8.000 $, Max loss limit 4.000 $):
-- der Radar zeigte bei zwei 150k-Challenge-Konten mit Balance ~153.200 einen Abstand von ~7.198 $ zur Liquidation. Ursache: die Zeile
-- stand seit sql/2026-09-30_liq-kontoboden.sql als ANNAHME auf 'statisch' (Boden = Größe − Max DD = 146.000).
-- Richtig (Finn):
--   Boden = höchste Tagesend-Balance − 4.000 $ (EOD-Trailing).
--   Der Boden steigt nie über die Startgröße: ab 154.000 steht er fest bei 150.000, der Abstand wächst dann mit der Balance.
--   150.000 → 146.000 (4.000) · 153.198 → 149.198 (4.000) · 154.000 → 150.000 (4.000) · 156.000 → 150.000 (6.000)
--   nach Rückgang von 153.198 auf 151.000 → Boden bleibt 149.198 (1.802)
-- Die Rechnung dafür gibt es schon (app.py liq_konto_boden, eod_trailing mit Lock) — es ändert sich nur diese Zeile, kein Code.
-- maxdd_usd 4.000 ist nur der Rückfall, falls accounts.max_drawdown fehlt (Wert des 150k-Kontos; andere Größen tragen ihren Max DD am
-- Konto). Die Zeile gilt für alle Kontotypen der Firma (kontotyp null) — belegt ist die Regel für die Challenge, Funded offen.
-- Nur Anzeige (Radar): Fusion-Hedge-Level bleiben unverändert. Selbsttest: tools/selftest_liq_regeln.py, Abschnitt 10.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

update public.liq_regeln
   set maxdd_art = 'eod_trailing',
       maxdd_usd = 4000,
       maxdd_lock_ueber_groesse_usd = 0,
       notiz = 'Finn 05.10.2026 (Futures Flex 150K Challenge: Profit target 8.000 $, Max loss limit 4.000 $): EOD-Trailing-Drawdown '
            || '4.000 $ — Boden = höchste Tagesend-Balance − 4.000, steigt nie über die Startgröße (150k: ab 154.000 fest bei 150.000). '
            || 'Ersetzt die Annahme „statisch" vom 30.09.2026. maxdd_usd nur Rückfall ohne accounts.max_drawdown (150k). '
            || 'Keine eigene Liq-Regel — nur Konto-Boden. Offen: Funded und andere Größen nicht belegt.',
       quelle = 'Finn 05.10.2026 (Screenshot FundedNext Futures Flex 150K Challenge, über den Master)'
 where lower(firma) = 'fundednext futures';

-- Falls die Zeile fehlt (kontoboden-Datei nie gelaufen): anlegen. Einmalig, nicht doppelt.
insert into public.liq_regeln (firma, kontotyp, art, maxdd_art, maxdd_usd, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'FundedNext Futures', null, null, 'eod_trailing', 4000, 0,
       'Finn 05.10.2026 (Futures Flex 150K Challenge: Profit target 8.000 $, Max loss limit 4.000 $): EOD-Trailing-Drawdown '
       || '4.000 $ — Boden = höchste Tagesend-Balance − 4.000, steigt nie über die Startgröße (150k: ab 154.000 fest bei 150.000). '
       || 'maxdd_usd nur Rückfall ohne accounts.max_drawdown (150k). Keine eigene Liq-Regel — nur Konto-Boden. '
       || 'Offen: Funded und andere Größen nicht belegt.',
       'Finn 05.10.2026 (Screenshot FundedNext Futures Flex 150K Challenge, über den Master)'
 where not exists (select 1 from public.liq_regeln where lower(firma) = 'fundednext futures');

-- Prüfen:
-- select id, firma, kontotyp, art, maxdd_art, maxdd_usd, maxdd_lock_ueber_groesse_usd, left(notiz, 80), quelle
--   from public.liq_regeln where lower(firma) = 'fundednext futures';

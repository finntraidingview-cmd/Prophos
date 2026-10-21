-- Lucid: Max Drawdown ist EOD-Trailing wie bei Tradeify (Finn 21.10.2026 ~22:05 Dubai: „bei Lucid 1:1 die gleiche Regel wie bei Tradeify,
-- nur 50 % statt 40 % Consistency"; Lucid-Dashboard: LucidFlex 150K …0002 „EOD DRAWDOWN · BREACHED", MLL 149.945 bei Balance 149.926).
-- liq_regeln Zeile 12 stand seit 30.09. auf der Annahme „statisch" (Größe − Max DD = 145.500) → Prophos sah den Blow nicht.
-- Jetzt eod_trailing: Boden = höchste Tages-End-Balance − Max DD des Kontos (accounts.max_drawdown, 150k 4.500 / 100k 3.000),
-- wie Tradeify Challenge. Keine feste Liq je Trade (art/betrag bleiben leer, die Größen haben unterschiedliche DD).
update liq_regeln
   set maxdd_art = 'eod_trailing',
       notiz = 'Finn 21.10.2026: Lucid wie Tradeify — Max Drawdown EOD-Trailing ab höchster Tages-End-Balance (Dashboard „EOD DRAWDOWN", MLL), '
            || 'Betrag = accounts.max_drawdown (150k 4.500, 100k 3.000). Vorher Annahme statisch (30.09.).',
       quelle = 'Finn 21.10.2026 + Lucid-Dashboard (LucidFlex 150K …0002 breached, MLL 149.945)',
       updated_at = now()
 where id = 12 and firma = 'Lucid Trading';

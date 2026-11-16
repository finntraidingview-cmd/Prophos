-- LF1d (Master 16.11.2026): liq_regeln FundedNext Futures Flex 50k — eigene Datei, damit der Radar richtig rechnet (getrennt vom Planer-Profil
-- sql/2026-11-16_fnf_flex_50k.sql). Idempotent, nicht angewendet. Unabhängig von der Reihenfolge zu sql/2026-11-16_lucid_flex_50k.sql (id vergibt die DB).
--
-- Liquidation für Radar und Hedge (liq_regeln), FNF Futures 50k — analog Lucid 50k, aber OHNE Daily Loss:
--   funded:       nur MLL 1.500 $ EOD trailing, Lock bei Größe + 100 (50.100) — maxdd_usd 1.500 als Rückfall ohne accounts.max_drawdown (die allgemeine Zeile id 11 hat 4.000)
--   winning_days: Boden Größe + 100 (50.100) fest, wie Tradeify/Lucid winning_days (art 'boden') — nach dem Pump ist das MLL längst gelockt
-- id ist eine Identity-Spalte (GENERATED ALWAYS) — nicht mitgeben (Master 16.11.2026: max(id) + n brach live mit 428C9 ab, Fix wie 776f7d03).
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, maxdd_art, maxdd_lock_ueber_groesse_usd, maxdd_usd, notiz, quelle)
select 'FundedNext Futures', t.kontotyp, 50000, t.art, null, t.lock_start, 'eod_trailing', 100, 1500,
       'LF1b 16.11.2026: FundedNext Futures Flex 50k ' || t.text, 'FundedNext Help-Center „Flex FundedNext Account“ + Finn 16.11.2026 (über den Master, LF1b)'
from (values ('funded', null::text, null::numeric, 'Funded — MLL 1.500 $ EOD trailing, Lock bei 50.100 (Größe + 100), KEIN Daily Loss.'),
             ('winning_days', 'boden', 100::numeric, 'Winning Days — Liq-Balance = Größe + 100 $ (50.100) fest, kein Daily Loss (wie Tradeify/Lucid winning_days).'))
     as t(kontotyp, art, lock_start, text)
where not exists (select 1 from public.liq_regeln l where l.firma = 'FundedNext Futures' and l.kontotyp = t.kontotyp and l.groesse = 50000);

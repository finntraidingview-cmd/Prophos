-- Lucid Winning Days wie Tradeify (Finn 23.10.2026: „Lucid ist 1:1 die gleichen Regeln wie Tradeify, alles ganz genau gleich").
-- Liquidation eines Lucid-Kontos vom Typ winning_days = Kontogröße + 100 $ (150k: 150.100), fest — genau wie die Zeile
-- Tradeify/winning_days (id 7). Ohne diese Zeile fiel Lucid-WD auf die generische Zeile (alle, winning_days, wie funded) zurück.
-- Nur DML, idempotent. Rückbau: delete from liq_regeln where firma = 'Lucid Trading' and kontotyp = 'winning_days';

insert into liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, stufen, wie_kontotyp,
                        maxdd_art, maxdd_lock_ueber_groesse_usd, maxdd_usd, notiz, quelle)
select 'Lucid Trading', 'winning_days', null, 'boden', null, 100, null, null,
       'eod_trailing', 100, null,
       'Lucid wie Tradeify: Liq-Balance = Kontogröße + 100 $ (150k: 150.100), fest, sobald zu Winning Days verschoben (Kopie von Tradeify/winning_days).',
       'Finn 23.10.2026 („Lucid 1:1 gleiche Regeln wie Tradeify")'
where not exists (select 1 from liq_regeln where firma = 'Lucid Trading' and kontotyp = 'winning_days');

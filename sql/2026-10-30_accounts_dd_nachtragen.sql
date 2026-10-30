-- VORSCHLAG, NICHT EINGESPIELT (S3, 30.10.2026) — Max Drawdown für CFD-Konten ohne Wert nachtragen, nur auf Finns Wort.
-- Anlass: Finn 14:5x, Nachfolger ohne Max Drawdown. Diese Konten kamen übers Account-Modal: Drawdown optional, account_size/starting_balance schreibt es nie.
-- Quelle: aktive Phase-1-Vorlage gleicher Firma und Größe, Größe aus dem Namen („100k …"). Finn: Phase 1 und Phase 2 haben denselben Drawdown.
-- Bewusst nicht dabei: FundingPips (Standard/Flex, 10.000 oder 12.000 ist Wissen je Konto), funded_cfd (Regel von Finn deckt nur die Phasen), Größen ohne Vorlage.
-- Prüfen vor dem Update: Gruppe (nur Hermann Technologies?) und die Vorschau unten. Mehrfach ausführbar, schreibt nur leere Felder.

-- Vorschau
select a.id, a.user_id, a.name, a.firm, a.account_type, a.external_id, v.max_drawdown as neu
  from accounts a
  join bulk_vorlagen v on v.aktiv and v.account_type = 'phase1' and lower(v.firm) = lower(a.firm)
   and coalesce(v.account_size, v.starting_balance) = (substring(a.name from '(\d{2,3})\s*k\M'))::numeric * 1000
 where a.max_drawdown is null and a.account_type in ('phase1', 'phase2') and a.firm <> 'FundingPips'
 order by a.firm, a.created_at desc;

-- Update (erst nach der Vorschau)
-- update accounts a
--    set max_drawdown = v.max_drawdown
--   from bulk_vorlagen v
--  where v.aktiv and v.account_type = 'phase1' and lower(v.firm) = lower(a.firm)
--    and coalesce(v.account_size, v.starting_balance) = (substring(a.name from '(\d{2,3})\s*k\M'))::numeric * 1000
--    and a.max_drawdown is null and a.account_type in ('phase1', 'phase2') and a.firm <> 'FundingPips';

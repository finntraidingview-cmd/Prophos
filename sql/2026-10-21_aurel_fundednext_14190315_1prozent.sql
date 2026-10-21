-- Aurel FundedNext 100k …0315 (Funded CFD) hat eine 1-%-Risikoregel (Finn 21.10.2026 ~17:05 Dubai: „bei Aurels FundedNext 1 % ändern, dass der
-- 1 % Risk Limit hat, dass man es visuell sieht"). Wie im Konto-Popup „Max Risiko / Trade" (accounts.max_risiko_trade, Konto wird in der
-- Liste markiert) + Zusatz im Namen wie bei Jacob …7924 („· 1% RULE"). 1 % von 100.000 = 1.000 $.
update accounts
   set max_risiko_trade = 1000,
       name = '100k 14190315 → Funded · 1% RULE'
 where id = '6e5db5c7-c79d-4d64-b24d-3a5757d27a94'
   and name = '100k 14190315 → Funded';

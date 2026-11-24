-- FZ2 (Finn 24.11.2026): Ina FundedNext 100k On Demand …0774 (accounts 74afba19-5f97-4bd9-94f2-5660a67aba2f) → Waiting for Payout.
-- Warum: Profit 2.152,54 $ (tv_balance 102.152,54) ≥ Firmen-Minimum 2.000 $, Consistency 770,74 / 2.152,54 = 35,8 % ≤ 40 %. Prophos hielt das Konto
-- gegen das gewürfelte Planer-Ziel 2.197 $ fest („fehlen 45 $“). Der Code-Fix FZ2 stellt solche Konten künftig selbst um (fcp_konto_rechnen „ziel“);
-- diese Zeile zieht Ina einmal von Hand nach, wie es der Planer-Lauf (app.py, Auto-Waiting) täte.
-- Idempotent: nur, wenn das Konto noch Funded CFD ist und noch nicht wartet. Keine offenen Pläne am Konto (geprüft 24.11. ~19:30 Dubai).
-- NUR DATEN, nicht eingespielt — Master spielt nach Finns Wort ein (execute_sql).
update accounts
   set waiting_payout_since = now()
 where id = '74afba19-5f97-4bd9-94f2-5660a67aba2f'
   and account_type = 'funded_cfd'
   and waiting_payout_since is null
returning id, name, tv_balance, waiting_payout_since;

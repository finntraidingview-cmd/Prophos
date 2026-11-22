-- WP2 Daten-Fix (23.11.2026, Befund WP1): Funded-CFD-Konten, die nach einem Payout zu Unrecht auf „Waiting for Payout“ stehen.
-- NUR VORBEREITET — nicht eingespielt. Einspielen erst auf Finns Wort und erst NACH dem Push von WP2 (fcp_payout_lesung_fehlt):
-- ohne den Fix stellt der Funded-CFD-Planer Konto A im nächsten Lauf (5 min) sofort wieder auf Waiting.
-- Jede Zeile hängt an fester id + Typ funded_cfd + Waiting gesetzt; Konto D zusätzlich an der Lesung. Passt der Zustand nicht mehr, ändert sie nichts.

-- Konto A — FundedNext 100k …7821 (On Demand). Payout angefragt 18.11. 22:37 UTC, Auszahlung bestätigt 19.11. 13:14 UTC; letzte echte
-- Lesung 18.11. 14:35 UTC (104.915,95, vor der Anfrage). Mit WP2 hält der Planer das Konto ohne neue Lesung („Balance nach Payout noch nicht
-- gelesen — ↻ Balance lesen“), statt es wieder auf Waiting zu stellen. Danach ↻ Balance lesen: 100.000 → plant normal; noch 104.915,95 →
-- stellt der Planer wieder auf Waiting (dann im FundedNext-Dashboard prüfen, ob der Payout abging).
update accounts
   set waiting_payout_since = null
 where id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad'
   and account_type = 'funded_cfd'
   and waiting_payout_since is not null;   -- danach entscheidet der Planer mit WP2 selbst (ohne Lesung halten, mit Lesung nach der Zahl)

-- Konto D — FundedNext 100k …7785. Waiting seit 02.11. (Trade „erster_payout_refund“ +105,53 $), KEIN Payout in Prophos; echte Lesung
-- 19.11. 20:37 UTC (Auftrag mt5_balance) = 100.000,00 → der Gewinn ist schon weg. Waiting leeren, damit der Planer wieder plant.
-- Offen (Frage an Finn/Pascal): wurde der Refund direkt bei FundedNext ausgezahlt? Dann gehört er zusätzlich in Admin → Payouts nachgetragen.
update accounts
   set waiting_payout_since = null
 where id = '62c98b66-5fc1-417a-9f45-7daf46e19bcc'
   and account_type = 'funded_cfd'
   and waiting_payout_since is not null
   and tv_balance <= 100001
   and tv_balance_at > waiting_payout_since;

-- Konto B — FundedNext 100k …5964 und Konto C — FundingPips 100k …8534: KEIN Update. Echte Lesungen vom 22.11. (MT5-Update am Sonntag,
-- Terminals offen) zeigen die Balance unverändert nach dem letzten Trade (101.701,97 bzw. 101.528,60) — die Firmen haben laut Lesung nicht
-- abgezogen, Waiting ist nach der Regel richtig. Zurücksetzen hilft nicht (nächster Lauf stellt wieder um). Erst im Dashboard der Firma klären.
-- FRAGE an Finn (Konto B): Der Payout vom 18.11. steht in pending_payouts mit 10,00 € („Congratulations! Your Performance Reward has been
-- disbursed!“) — bei 1.701,97 $ Gewinn wirkt der Betrag falsch erfasst. Richtigen Betrag nennen; die Korrektur geht über Admin → Payouts,
-- nicht über diese Datei:
--   select id, amount, currency, requested_at, received_at, liegt_bei from pending_payouts
--    where account_id = 'ce8e742d-0674-4ec0-9b48-2e5200870bc9' order by created_at;

-- Kontrolle danach:
-- select id, name, waiting_payout_since, tv_balance, tv_balance_at from accounts
--  where id in ('27f94392-6d8d-4ccf-92a0-9edf5c008aad', '62c98b66-5fc1-417a-9f45-7daf46e19bcc');

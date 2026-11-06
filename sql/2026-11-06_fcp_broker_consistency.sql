-- CS1 · CONSISTENCY LAUT BROKER (Finn 06.11.2026, The5%ers-Screenshots): bei Funded-CFD-Konten mit Hand-Trades stimmt die DB-Historie nicht.
-- Der Funded-CFD-Planer (fcp_cons_finn) rechnet bisher bester Tag B und Summe der Gewinn-Tage W nur aus trade_plans. Neu:
-- accounts.fcp_broker = {at, bester_tag, zyklus_gewinn, balance, quelle}. Der Planer nimmt diese Werte als Basis, solange seit `at` kein neuer
-- Payout kam (Zyklus-Beginn ≤ Berlin-Tag von `at`), und zählt nur Trades dazu, die NACH `at` beendet wurden:
--   B = max(bester_tag, bester Tag nach at) · W = zyklus_gewinn + Gewinn-Tage nach at · Serie/heute nur aus Trades nach at.
-- Nach dem nächsten Payout gilt wieder die DB-Zählung (der Eintrag bleibt stehen, wirkt aber nicht mehr).
-- REIHENFOLGE: (1) DDL hier, (2) Code-Push (liest fcp_broker; ohne Code wirkt die Spalte nicht), (3) Konto-Zeilen unten.
-- NICHT eingespielt (Slave 3, Konstrukt CS1). Idempotent.

-- (1) Spalte
alter table public.accounts add column if not exists fcp_broker jsonb;

-- (2) KONTO-VORLAGE: je Konto nur diese drei Zahlen aus dem The5%ers-Screenshot eintragen (Balance, bester Tag, Zyklusgewinn), Konto-ID-Präfix
--     anpassen. waiting_payout_since wird geleert, damit der Planer wieder plant; payout_ready_at (Finns Payout-Termin) bleibt stehen.
--     Moritz The5%ers 200k …26776641 (8100ae6c), Screenshot 06.11.2026: Balance 201.477, Payout verfügbar 1.476,59, Consistency
--     „Days 100,00 % – Max 50 % profit one day – Out of range" → bester Tag = Zyklusgewinn = 1.476,59.
update public.accounts
   set fcp_broker = jsonb_build_object('at', now(), 'quelle', 'the5ers_screenshot',
                                       'balance', 201476.59, 'bester_tag', 1476.59, 'zyklus_gewinn', 1476.59),
       waiting_payout_since = null
 where id = '8100ae6c-5431-4d72-92c7-4c1c4cb69e66'
   and account_type = 'funded_cfd'
returning id, name, fcp_broker, waiting_payout_since, payout_ready_at;

-- Rücknahme je Konto: update public.accounts set fcp_broker = null where id = '<konto-id>';

-- CS1 · CONSISTENCY LAUT BROKER (Finn 06.11.2026, The5%ers-Screenshots): bei Funded-CFD-Konten mit Hand-Trades stimmt die DB-Historie nicht.
-- Der Funded-CFD-Planer (fcp_cons_finn) rechnet bester Tag B und Summe der Gewinn-Tage W sonst nur aus trade_plans. Seit CS1 (app.py fcp_tw_broker)
-- liest er accounts.fcp_ziel.broker = {at, bester_tag, zyklus_gewinn, balance, quelle} — KEINE neue Spalte (Master 06.11.2026), der Unterschlüssel
-- liegt im bestehenden jsonb fcp_ziel; der Planer behält ihn beim Würfeln des festen Ziels. Gültig, solange seit `at` kein neuer Payout kam;
-- B = max(bester_tag, bester Tag nach at), W = zyklus_gewinn + Gewinn-Tage nach at. Nach dem nächsten Payout wieder die DB-Zählung.
-- REIHENFOLGE: erst den Code (CS1) pushen, dann die Konto-Zeile(n). Reines Daten-Update, idempotent. NICHT eingespielt (Slave 3).

-- KONTO-VORLAGE: je Konto Block kopieren, Konto-ID + drei Zahlen aus dem Screenshot eintragen (Balance, bester Tag, Zyklusgewinn).
-- waiting_payout_since wird geleert, damit der Planer wieder plant; payout_ready_at (Finns Payout-Termin) bleibt.

-- Moritz The5%ers 200k …26776641 (8100ae6c), Screenshot 06.11.2026: Balance 201.477, Payout verfügbar 1.476,59, Consistency
-- „Days 100,00 % – Max 50 % profit one day – Out of range" → bester Tag = Zyklusgewinn = 1.476,59.
-- Erwartet danach (Planer, The5%ers 50 %): Trade 1 ≈ 729 $, Trade 2 ≈ 807 $ an einem anderen Tag → ≈ 203.012,59, bester Tag ≈ 49 %.
update public.accounts
   set fcp_ziel = coalesce(fcp_ziel, '{}'::jsonb) || jsonb_build_object('broker', jsonb_build_object(
         'at', now(), 'quelle', 'the5ers_screenshot', 'balance', 201476.59, 'bester_tag', 1476.59, 'zyklus_gewinn', 1476.59)),
       waiting_payout_since = null
 where id = '8100ae6c-5431-4d72-92c7-4c1c4cb69e66'
   and account_type = 'funded_cfd'
returning id, name, fcp_ziel, waiting_payout_since, payout_ready_at;

-- Rücknahme je Konto: update public.accounts set fcp_ziel = fcp_ziel - 'broker' where id = '<konto-id>';

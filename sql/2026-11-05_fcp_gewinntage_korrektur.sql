-- GEWINNTAGE VON HAND bei Funded CFD (GT2, 05.11.2026, Finn — Blue Guardian 100k …7770 Funded CFD: „Der erste Tag ist durch. Ich wollte jetzt gerade
-- unter Settings dem quasi +1 Tag hinzufügen, aber ich kann es hier nirgends sehen … Wenn ich auf den Account draufdrücke, kann ich diese Gewinntage nicht
-- bearbeiten“). NICHT automatisch einspielen, Finn/Master spielt ein — (1) DDL per apply_migration, (2a)/(2b) auskommentiert, erst auf Finns Wort.
--
-- (1) accounts.fcp_gewinntage = {zyklus, korrektur, at}: ± Tage von Hand für den Payout-Zyklus `zyklus` (Account bearbeiten → „Gewinntage (dieser
--     Payout-Zyklus)“ → Setzen). Planer (fcp_planen), Radar/Abhak (zw_funded_cfd) und Konto-Seite (/konto-ziele) rechnen Zählung + Korrektur
--     (app.py fcp_gt_korrektur). Ein anderer Zyklus (nach dem nächsten Payout) → Korrektur wirkt nicht mehr, kein Zurücksetzen nötig. Fehlt die Spalte,
--     zählt alles wie bisher, das Feld meldet beim Setzen „Spalte fehlt“.
--
-- (2) …7770 heute (Berlin 05.11.2026), nachgerechnet aus der DB:
--       e8fa35d4 Gewinntag-Trade (Echo, SELL 1,53)   master_pl 447,83   Balance danach 100.447,83 (Start 100.000)
--       7869ea6c Hand-Nachtrade (Echo, BUY 0,4)      master_pl  50,00 (pl_quelle 'hand', beim Abhaken von Hand)   Balance danach 100.534,71
--     Die Zählung summiert schon alle abgeschlossenen Trades je Berlin-Tag (auch Hand-Trades) — 447,83 + 50,00 = 497,83 < 500 → 0/3.
--     Laut zwei Balance-Lesungen (mt5_baseline.bal_nach + final.master_balance, kein anderer Trade dazwischen) brachte der Nachtrade +86,88 $:
--     100.534,71 − 100.447,83. Mit dem echten Wert: 447,83 + 86,88 = 534,71 ≥ 500 → 1/3.
--     (2a) EMPFOHLEN: master_pl des Nachtrades auf die Balance-Differenz korrigieren — dann zählt Prophos den Tag von selbst, und Ziel/Consistency
--          rechnen mit der echten Zahl. Guard: nur, wenn noch genau der Hand-Wert 50,00 drinsteht.
--     (2b) ALTERNATIVE (wenn die 50,00 bewusst so stehen sollen): Korrektur +1 im Zyklus 1 (Konto ohne Payout) — nur EINS von beiden einspielen.
--
-- Rückbau: (2a) update public.trade_plans set master_pl = 50.00 where id = '7869ea6c-2678-450e-8194-bae53e0290a0';
--          (2b) update public.accounts set fcp_gewinntage = null where id = '6d742532-26a1-4fab-82fb-3c03cd50b62d';
--          (1)  alter table public.accounts drop column if exists fcp_gewinntage;

-- (1)
set lock_timeout = '5s';
alter table public.accounts add column if not exists fcp_gewinntage jsonb;
comment on column public.accounts.fcp_gewinntage is
  'GT2 05.11.2026: Gewinntage von Hand je Payout-Zyklus {zyklus, korrektur, at} — Funded CFD mit Mindest-$-Tagen (Blue Guardian). Gilt nur im Zyklus zyklus.';

-- (2a) EMPFOHLEN — …7770 Hand-Nachtrade auf die Balance-Differenz (+86,88 $). Auskommentiert (Fremd-Review GT2): die Datei als Ganzes per apply_migration
--      legt nur die Spalte an; (2a) bzw. (2b) erst auf Finns Wort einzeln per execute_sql. NICHT (2a) einspielen, wenn im Modal schon „1 von 3“ gesetzt
--      wurde — sonst zählt der Tag doppelt (2/3); dann zuerst die Korrektur leeren (Rückbau 2b) oder (2a) weglassen.
-- update public.trade_plans
--    set master_pl = 86.88
--  where id = '7869ea6c-2678-450e-8194-bae53e0290a0'
--    and master_account_id = '6d742532-26a1-4fab-82fb-3c03cd50b62d'
--    and master_pl = 50.00 and pl_quelle = 'hand';

-- (2b) ALTERNATIVE — statt (2a): +1 Tag von Hand im Zyklus 1
-- update public.accounts set fcp_gewinntage = jsonb_build_object('zyklus', 1, 'korrektur', 1, 'at', now())
--  where id = '6d742532-26a1-4fab-82fb-3c03cd50b62d' and account_type = 'funded_cfd';

-- Kontrolle (nur lesen): Tagessumme …7770 am 05.11. (Berlin) — muss nach (2a) 534,71 sein
-- select (ended_at at time zone 'Europe/Berlin')::date tag, sum(master_pl) from public.trade_plans
--  where master_account_id = '6d742532-26a1-4fab-82fb-3c03cd50b62d' and status in ('completed', 'review') group by 1;

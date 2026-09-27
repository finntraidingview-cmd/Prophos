-- Emin (6cceb3f3-…) startet ab 27.09.2026 mit dem Tracken der Finanzen bei 0.
-- Finn 27.09.2026: „neue Ära bei Emin erstellen, die alte nicht löschen, nur archivieren“.
-- Kapitel sind global (keine Nutzer-Spalte) — ein neues Kapitel hätte Finn mit
-- zurückgesetzt. Deshalb: Emins abgeschlossene Trades aus „Ohne Hedge“ (2) ins
-- Archiv „Hedge-Ära“ (1) schieben. Nichts wird gelöscht.
-- Bleibt bewusst in Kapitel 2: das FTMO-Konto e9e7f60d (Kauf −1.000 €, 25.09.)
-- und sein noch offener Trade 457ace32 — die laufen weiter.

update public.trade_plans
   set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f'
   and kapitel_id = 2
   and status = 'completed';

-- Nachtrag 27.09.2026 16:15 (Finn: „da soll alles resetet“, Screenshot zeigte „Alle“ mit −11.450,79 €):
-- auch der FTMO-Kauf und der offene FTMO-Trade gehen ins Archiv. Das Konto e9e7f60d selbst
-- bleibt in Kapitel 2 — Payouts darauf erben per Trigger das Konto-Kapitel und zählen damit neu.
update public.transactions set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 2;
update public.trade_plans set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 2;

-- Die Kachel „Aktueller Zyklus“ rechnet über ALLE Buchungen (ohne Kapitel-Filter) minus
-- Baseline der letzten Abrechnung — deshalb eine Abrechnung als Nullpunkt (Emin behält 100 %).
insert into public.finanzen_settlements (user_id, cycle_netto, cumulative_baseline, profit_share_pct, client_amount, house_amount, note)
select '6cceb3f3-dc78-48ee-8668-26081da3e70f', s, s, 0, 0, s, 'Neustart Finanz-Tracking 27.09.2026 (alte Ära archiviert)'
  from (select coalesce(sum(amount), 0) s from public.transactions
         where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f') x;

-- Umschalter oben auf „Ohne Hedge“ (gesynct über user_settings 'kapitel').
update public.user_settings set value = '{"id":2}'::jsonb, updated_at = now()
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and key = 'kapitel';

-- Nachtrag 2 (27.09.2026 16:45, Finn: Payout auf „50k Funding Pips 20368773 → Funded“ taucht
-- nirgends auf): Buchungen/Payouts erben per Trigger set_kapitel das Kapitel des KONTOS — Emins
-- Konten standen noch in Kapitel 1, also landete jeder neue Payout unsichtbar im Archiv.
-- Emins Konten ziehen deshalb ins aktuelle Kapitel. Bestehende Buchungen behalten ihr eigenes
-- kapitel_id (Trigger greift nur beim Insert) und bleiben archiviert.
update public.accounts set kapitel_id = 2
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 1;
-- Die zwei Payout-Anfragen von 16:41/16:42 (je 754 €) nachträglich ins aktuelle Kapitel.
update public.pending_payouts set kapitel_id = 2
 where id in ('c16b7e19-2925-42ba-ba23-f4f3a61964d7', 'b96e1087-10e8-42f6-b8b5-bd88c140fe18');

-- Nachtrag 3 (27.09.2026 abends, Finn: „alles resetten, einmal noch … die Accounts, die heute
-- eingekauft wurden, drin lassen“; Kapitel-Karte zeigte „Ohne Hedge · Kauf 25.732 €“, weil
-- Nachtrag 2 alle Konten samt Kaufpreis ins Kapitel 2 gezogen hatte). Neue Buchungen von Emin
-- zählen seit sql/2026-09-27_admin_zugang_buchung_nach_datum.sql nach Datum, die Konten können
-- deshalb zurück in die alte Ära — bis auf die 5 heute gekauften (3× Tradeify 150k, 2× FundingPips 100k).
update public.accounts set kapitel_id = 1
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f'
   and id not in ('565c1380-acef-413a-a81f-852075f136a2', '3e0cb5c7-e343-461c-ae24-46ae997d9544',
                  'e416f204-2897-4a47-8822-a0c317a48590', '3b6561a2-5175-47f9-9997-768b4a64914a',
                  'b4d48b09-2c9f-4748-8dfd-9288868762c4');

-- Doppelte Payout-Anfrage (754 € FundingPips, 16:42 — zweimal gespeichert, als der Payout
-- wegen des Kapitel-Bugs unsichtbar war): die zweite weg, die erste als erhalten gebucht (Finn).
delete from public.pending_payouts where id = 'b96e1087-10e8-42f6-b8b5-bd88c140fe18' and status = 'pending';
with tx as (
  insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated)
  values ('6cceb3f3-dc78-48ee-8668-26081da3e70f', '20cf7807-d6c3-4805-8b54-cebc7bc317c2', '50k Funding Pips 20368773 → Funded',
          'FundingPips', 'payout', 754, 'EUR', '2026-09-27', 'angefragt 27.09.26', false)
  returning id)
update public.pending_payouts set status = 'received', received_at = '2026-09-27', received_tx_id = (select id from tx), updated_at = now()
 where id = 'c16b7e19-2925-42ba-ba23-f4f3a61964d7' and status = 'pending';

-- Nullpunkt neu: Baseline = alles, was in der alten Ära liegt; der Zyklus zeigt damit genau die
-- Käufe von heute und den Payout.
update public.finanzen_settlements
   set cumulative_baseline = (select coalesce(sum(amount), 0) from public.transactions
                               where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 1),
       cycle_netto = (select coalesce(sum(amount), 0) from public.transactions
                       where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 1),
       house_amount = (select coalesce(sum(amount), 0) from public.transactions
                        where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f' and kapitel_id = 1)
 where user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f'
   and note = 'Neustart Finanz-Tracking 27.09.2026 (alte Ära archiviert)';

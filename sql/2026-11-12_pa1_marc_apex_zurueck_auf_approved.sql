-- PA1-Nachtrag (Finn 12.11.2026 ~20:10 Dubai: „Bitte nur wieder zurück auf approved.“): bei Marc (user 6c206a34-c4a7-4352-8097-bb17366bcea1) wurden zwei
-- Apex-Payouts am 10.11. auf „Erhalten“ gedrückt, damit die Konten wieder fahren — in Wahrheit sind sie nur approved, das Geld ist nicht da.
-- ERST NACH dem PA1-Push (app.py payout_sperrt) UND nach sql/2026-11-12_pa1_payout_approved.sql einspielen — sonst sperrt die wieder offene Anfrage die
-- Konten für den WD-Farmer. Nur auf Finns/Masters OK (löscht zwei Finanzen-Buchungen).
--
-- Was passiert (gelesen 12.11.2026):
--  pending_payouts 410916f9-11c3-41b3-b9e1-50a2a0759bb8 · 150k PAAPEX6843320000002 → Winning Days · 2.233,55 EUR · angefragt 09.11. · received 10.11.
--  pending_payouts 404773a7-a85d-4a9d-b8a6-c8a302e9f175 · 100k PAAPEX6843320000005 → Funded       · 1.786,84 EUR · angefragt 09.11. · received 10.11.
--    → status pending, received_at/received_tx_id leer, approved_at = received_at (10.11. 00:00 UTC = 04:00 Dubai), approved_von „Finn 12.11.: zurück auf approved“.
--  transactions 2c31a1b9-2de1-4b49-b129-f5c818eecdc8 · kind payout · 2.233,55 EUR · occurred_at 10.11. · Apex Trader · kapitel 2   → GELÖSCHT
--  transactions da7e8678-95c3-4eec-a195-ad6389d1e4f5 · kind payout · 1.786,84 EUR · occurred_at 10.11. · Apex Trader · kapitel 2   → GELÖSCHT
--  Zusammen −4.020,39 EUR Payouts in Marcs Finanzen. Es gibt keinen Weg „Erhalten rückgängig“ im Code; das Gegenstück zum Erhalten (Insert der Buchung) ist
--  das Löschen genau dieser Zeile. Keine Fremdschlüssel und keine Lösch-Trigger auf transactions. Sonst nichts in Finanzen.
--  Warum löschen statt nur entkoppeln: fcp_payouts_zaehlen / Apex-Zyklus zählen eine Buchung ohne received_tx_id-Verweis als EIGENEN Payout — entkoppelt
--  stünden die Konten bei 2 statt 1 Payout (Zyklus spränge). Gelöscht bleibt es 1 Payout (die Anfrage), Zyklus-Start bleibt die Anfrage vom 09.11.
--  Konten bleiben frei: approved sperrt nicht (payout_sperrt), waiting_payout_since/payout_ready_at sind leer und werden nicht angefasst, Zyklus unverändert.
--  Seit dem 10.11. sind auf den Konten schon 3 bzw. 2 Pläne gestartet → ein späteres „zurück“ beim Approved lehnt der Server ab (gewollt).
-- Alles oder nichts: jede Abweichung vom gelesenen Stand bricht ab, nichts wird geändert. Idempotent (zweiter Lauf: schon approved → Hinweis, nichts geändert).

do $$
declare n_p int; n_t int;
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'pending_payouts' and column_name = 'approved_at') then
    raise exception 'Spalte approved_at fehlt — erst sql/2026-11-12_pa1_payout_approved.sql einspielen';
  end if;
  if (select count(*) from public.pending_payouts where id in ('410916f9-11c3-41b3-b9e1-50a2a0759bb8', '404773a7-a85d-4a9d-b8a6-c8a302e9f175')
        and status = 'pending' and approved_at is not null and received_tx_id is null) = 2 then
    raise notice 'schon zurück auf approved — nichts geändert';
    return;
  end if;

  delete from public.transactions t
   using public.pending_payouts p
   where p.id in ('410916f9-11c3-41b3-b9e1-50a2a0759bb8', '404773a7-a85d-4a9d-b8a6-c8a302e9f175')
     and p.status = 'received' and p.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
     and t.id = p.received_tx_id and t.user_id = p.user_id and t.kind = 'payout' and t.amount = p.amount and t.account_id = p.account_id
     and t.id in ('2c31a1b9-2de1-4b49-b129-f5c818eecdc8', 'da7e8678-95c3-4eec-a195-ad6389d1e4f5');
  get diagnostics n_t = row_count;
  if n_t <> 2 then
    raise exception 'erwartet 2 Buchungen, gefunden % — Stand weicht ab, nichts geändert', n_t;
  end if;

  update public.pending_payouts
     set status = 'pending', approved_at = received_at::timestamptz, approved_von = 'Finn 12.11.: zurück auf approved',
         received_at = null, received_tx_id = null, updated_at = now()
   where id in ('410916f9-11c3-41b3-b9e1-50a2a0759bb8', '404773a7-a85d-4a9d-b8a6-c8a302e9f175')
     and status = 'received' and user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
     and received_tx_id in ('2c31a1b9-2de1-4b49-b129-f5c818eecdc8', 'da7e8678-95c3-4eec-a195-ad6389d1e4f5');
  get diagnostics n_p = row_count;
  if n_p <> 2 then
    raise exception 'erwartet 2 Anfragen, gefunden % — nichts geändert', n_p;
  end if;
end $$;

-- Kontrolle
-- select id, status, approved_at, approved_von, received_at, received_tx_id from public.pending_payouts
--  where id in ('410916f9-11c3-41b3-b9e1-50a2a0759bb8', '404773a7-a85d-4a9d-b8a6-c8a302e9f175');
-- select count(*) from public.transactions where id in ('2c31a1b9-2de1-4b49-b129-f5c818eecdc8', 'da7e8678-95c3-4eec-a195-ad6389d1e4f5');   -- 0

-- Wiederherstellen (nur falls nötig: die zwei Buchungen exakt wie vorher, danach in pending_payouts status received / received_at 2026-11-10 /
-- received_tx_id wieder setzen und approved_at leeren):
-- insert into public.transactions (id, user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated, created_at, updated_at, kapitel_id) values
--  ('2c31a1b9-2de1-4b49-b129-f5c818eecdc8', '6c206a34-c4a7-4352-8097-bb17366bcea1', '2aa6f1a9-ac0f-43a5-80d9-08e1f15c3a4d', '150k PAAPEX6843320000002 → Winning Days', 'Apex Trader', 'payout', 2233.55, 'EUR', '2026-11-10',
--   'Aus Admin angefragt · vorher: Winning Days 4/5 (alter Zähler) · angefragt 09.11.2026 · lag bei unklar · 10.11. 00:01 · Mail ohne eindeutige Zuordnung: PA Payout Approved', false, '2026-11-10 01:27:38.917733+00', '2026-11-10 01:27:38.917733+00', 2),
--  ('da7e8678-95c3-4eec-a195-ad6389d1e4f5', '6c206a34-c4a7-4352-8097-bb17366bcea1', '6f7f4acd-3d1b-41f3-bf3b-c9f234889f35', '100k PAAPEX6843320000005 → Funded', 'Apex Trader', 'payout', 1786.84, 'EUR', '2026-11-10',
--   'Aus Admin angefragt · vorher: Winning Days 1/5 (alter Zähler) · angefragt 09.11.2026 · lag bei unklar · 10.11. 00:01 · Mail ohne eindeutige Zuordnung: PA Payout Approved', false, '2026-11-10 01:27:31.694971+00', '2026-11-10 01:27:31.694971+00', 2);

-- 2026-10-29: Payout-Anfrage 899 € (ID Moritz, 28.10.2026 23:51 UTC = 29.10. 03:51 Dubai) wurde OHNE Account gespeichert
-- (Finanzen → Payout eintragen, Feld „Account" leer) — deshalb liefen Termin, Waiting-Reset und Balance-Lesung nicht.
-- Finn 29.10.2026 05:30 Dubai: gehört zum The5%ers-Konto, über das er gerade angefragt hat. Hier wird genau das nachgezogen, was
-- der normale Anfrage-Weg mit Konto getan hätte (prophos.html finModalSave, Zweig „Angefragt"):
--   1) pending_payouts: account_id / account_name / account_firm wie beim Insert aus dem Modal
--   2) accounts.waiting_payout_since leeren (wartetPayoutClear) — falls gesetzt
--   3) accounts.payout_ready_at = Anfragedatum + 14 Tage (CFD-Regel seit .1835) — nur wenn nicht schon später
-- Die Balance des Kontos wurde 28.10. 23:53 UTC schon gelesen (order_signale mt5_balance) — nichts weiter nötig.
-- Vorher belegt: genau 1 Anfrage (pending, ohne Account, 899 EUR) und genau 1 Konto (gleiche user_id, funded_cfd).
-- Wiederholbar: jede Zeile hat Wächter, ein zweiter Lauf ändert nichts.

begin;

update pending_payouts p
   set account_id   = a.id,
       account_name = a.name,
       account_firm = a.firm
  from accounts a
 where p.id = '79dd9cdd-3736-439b-9e1b-0dbc9d3fb2be'
   and a.id = '4bf43f54-7f2f-41c0-b810-b2ccf7fb0b34'
   and p.user_id = a.user_id
   and p.account_id is null;

update accounts
   set waiting_payout_since = null
 where id = '4bf43f54-7f2f-41c0-b810-b2ccf7fb0b34'
   and waiting_payout_since is not null;

update accounts
   set payout_ready_at = date '2026-10-28' + 14
 where id = '4bf43f54-7f2f-41c0-b810-b2ccf7fb0b34'
   and (payout_ready_at is null or payout_ready_at < date '2026-10-28' + 14);

commit;

-- Prüfen:
-- select p.account_id, p.account_firm, a.waiting_payout_since, a.payout_ready_at
--   from pending_payouts p join accounts a on a.id = p.account_id where p.id = '79dd9cdd-3736-439b-9e1b-0dbc9d3fb2be';

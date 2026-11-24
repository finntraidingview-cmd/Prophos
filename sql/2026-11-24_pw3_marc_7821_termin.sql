-- PW3 (Master 24.11.2026): Marc · FundedNext 100k On Demand …7821 (accounts 27f94392-6d8d-4ccf-92a0-9edf5c008aad)
-- Befund: Payout 18.11. angefragt, 19.11. erhalten (3.428,78 €), danach bis 24.11. 17:29 UTC nie gelesen → Echo/tv_balance eingefroren auf 104.915,95.
-- Der Funded-CFD-Planer hielt das am 23.11. für „Ziel erreicht“ (Waiting + O1 „Payout anfragbar ab“ = 2026-11-23). Waiting hat PW1 (.2308) zurückgestellt,
-- die Lesung 24.11. 17:29 UTC ergab 100.000,00 (tv_balance + mt5_live stehen darauf). Übrig: der Termin 2026-11-23 → Admin → Payouts zeigt
-- „seit gestern anfragbar“. On Demand hat keinen Termin (OD1) — leeren. Der Planer plant ab dem nächsten Lauf von selbst mit 100.000 (PW1: Abbuchung
-- beobachtet → neuer Zyklus), dafür ist nichts weiter nötig.
-- Idempotent: Sicherung nur einmal, Update nur, solange genau dieser Termin steht und das Konto On Demand / Funded CFD ist.

create table if not exists pw3_marc_7821_20261124 as
  select id, payout_ready_at, waiting_payout_since, tv_balance, tv_balance_at, now() as gesichert_at
  from accounts where id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad';

update accounts set payout_ready_at = null
 where id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad'
   and account_type = 'funded_cfd' and on_demand is true
   and payout_ready_at = '2026-11-23';

-- Kontrolle: payout_ready_at leer, waiting_payout_since leer, tv_balance 100000
select id, name, payout_ready_at, waiting_payout_since, tv_balance, tv_balance_at from accounts where id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad';

-- Zurück (nur falls nötig):
-- update accounts a set payout_ready_at = s.payout_ready_at from pw3_marc_7821_20261124 s where a.id = s.id;

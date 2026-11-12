-- Chris Apex 100k PAAPEX6687940000005 zurück auf Funded (Finn 13.11.2026 ~03:00 Dubai: „Der Account war aus Versehen bei Winning Days, obwohl er eigentlich
-- noch Funded ist … wieder in Funded Planern benutzt, bis er sein Ziel von +12K erreicht“). Finn hat um 02:57 „wieder Funded“ geklickt (account_type → funded);
-- der Funded-Planer hat sofort Plan cd164fc9 angelegt (Ziel 112.000 $, 2 NQ, Start 10:20). Offen blieben: wd_farm true (der WD-Farmer würde das Konto weiter
-- als WD-Kandidat führen → Doppelplan) und der Name „→ Winning Days“ (Konto-Namensregel). Beides hier. goal_kind bleibt wie bei den übrigen Apex-Fundeds.
update public.accounts
   set wd_farm = false, name = '100k PAAPEX6687940000005 → Funded', updated_at = now()
 where id = 'bf941721-972f-4c3c-863e-2cc409f02a59' and account_type = 'funded';

-- Finn 18.11.2026 (Screenshot „Braucht dich“: Jona 200k …7791 The5%ers „geblowt? Balance 100.800 $ am/unter dem Boden 180.000 $“, gelesen 200.000,01 $).
-- Befund: Konto 98bb2efa „200k 26847791 → Funded“ (angelegt 17.11. 15:19) hat cred_login 26847792 — die External ID wurde vom 100k-Konto
-- 562a1a8e (26847791, angelegt 15:17, Plan 31363c26 +799,90 $ → 100.799,90 $) übernommen. Die Boden-Prüfung zog über die gleiche External ID
-- die Balance des 100k-Kontos. Korrektur: External ID + Name des 200k-Kontos auf das echte Login 26847792 (Konto-Namensregel). Guard: Login frei.
update public.accounts a
set external_id = '26847792', name = '200k 26847792 → Funded', updated_at = now()
where a.id::text like '98bb2efa%' and a.external_id = '26847791' and a.cred_login = '26847792'
  and not exists (select 1 from public.accounts b where b.external_id = '26847792' and b.id <> a.id)
returning left(a.id::text,8) id, a.name, a.external_id, a.cred_login, a.tv_balance;

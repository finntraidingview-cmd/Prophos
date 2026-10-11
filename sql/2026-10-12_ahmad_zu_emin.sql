-- Neue ID Ahmad (Login 11.10.2026 22:14 UTC, Trigger legte sie in „Hermann Technologies") in die Gruppe „Emin" (Finn 12.10.2026).
-- Backend kennt die Zuordnung nach ≤ 60 s; damit auch raus aus den HT-Statistiken.
update public.id_gruppe_mitglied
   set gruppe_id = (select id from public.id_gruppen where name = 'Emin'), seit = now()
 where user_id = 'fb42b5c3-def9-4bc0-8b5b-bb2525b76ad8';

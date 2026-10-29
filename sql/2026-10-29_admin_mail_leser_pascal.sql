-- ID „Pascal“ auf die Leseliste admin_mail_leser (Finn 29.10.2026: „Finn + Pascal und Pascal sehen quasi alles, Emin sieht für Emin
-- die ganzen IDs.“). Die Liste gibt seit .1836 den Admin-Reiter „Kapital“ über alle Gruppen frei (kapital_app.py _gate) und — wie
-- schon für „Finn + Pascal“ — alle Mails unter Admin → Mail. Idempotent.

insert into public.admin_mail_leser (user_id, notiz)
values ('728b4d23-ff5c-45f9-b6de-9b75c1f9a78a', 'Pascal — Finn 29.10.2026: sieht alles wie Finn + Pascal (Kapital, Admin-Mail)')
on conflict do nothing;

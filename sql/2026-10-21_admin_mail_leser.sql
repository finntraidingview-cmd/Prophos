-- Admin → Mail: Freigabe nur fürs Mail-Lesen (21.10.2026, Finn ~04:00 Dubai, Build .1670: „Ich bin ja Finn + Admin … Kann ich alle
-- Mails nicht sehen?"). /admin/mail ließ nur Logins aus der Railway-Variable ADMIN_EMAILS durch; Finns Tages-Login „Finn + Pascal"
-- steht dort nicht → 403, Liste leer. ADMIN_EMAILS zu erweitern gäbe dem Login zugleich Rechnungen, Ausgleichen, Bot-Schalter und
-- kippte in der Liq-Ansicht das Kunde-Flag dieser ID. Deshalb diese eigene, enge Freigabe: eine Zeile = dieser Login sieht unter
-- Admin → Mail die Postfächer aller IDs der Standard-Sicht Hermann Technologies (wie ADMIN_EMAILS dort), sonst nichts.
-- Gate im Backend: _admin_mail_auth (app.py), 60 s gemerkt; Login darf im Admin nicht eingeschränkt sein (Verwalter/Gruppen-Mitglied nie).
-- Lesen/Schreiben nur Service-Key (RLS an, keine Policy) — kein Login kann sich selbst eintragen. Keine E-Mail im Code, nur die user_id.

create table if not exists public.admin_mail_leser (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  notiz      text,
  created_at timestamptz not null default now()
);

alter table public.admin_mail_leser enable row level security;

-- Finn + Pascal (finnh4799, Gruppe Hermann Technologies)
insert into public.admin_mail_leser (user_id, notiz)
values ('48f272b4-913e-4598-a06a-1dcc3d5679fb', 'Finn + Pascal — Finn 21.10.2026: alle Mails unter Admin → Mail')
on conflict (user_id) do nothing;

-- Weitere Leser: eine Zeile mehr, keine Code-Änderung. Entziehen:
-- delete from public.admin_mail_leser where user_id = '<uuid>';

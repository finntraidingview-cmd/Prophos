-- MAIL-REITER (Finn 16.10.2026: „Jedes Gmail ist ausschließlich für Prophos, ALLE Mails sollen rein. So simpel wie möglich … Jede ID
-- bekommt nur ihre eigenen Mails — logge ich mich als Aurel ein, sehe ich nur Aurels Gmail.")
-- Weg: Google-Apps-Script im jeweiligen Gmail-Konto schickt alle 5 min neue Mails an Railway POST /mail/eingang (Header X-Mail-Schluessel).
-- Railway sucht den Schlüssel über seinen SHA-256 in mail_schluessel, schreibt mit service role in mails. Das Frontend liest direkt per RLS.
-- Kein OAuth-Client, kein Passwort in der DB, der Klartext-Schlüssel steht nur im Script.

create table if not exists public.mails (
  id            bigint generated always as identity primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  gmail_msg_id  text not null,
  thread_id     text,
  von           text,
  an            text,
  betreff       text,
  datum         timestamptz,
  snippet       text,
  text          text,            -- Klartext, von Railway auf 50 KB gekürzt
  html          text,            -- HTML, von Railway auf 200 KB gekürzt; das Frontend zeigt es nur im sandbox-iframe ohne Skripte
  anhaenge      jsonb not null default '[]'::jsonb,   -- nur [{name, groesse, typ}], keine Inhalte
  gelesen       boolean not null default false,
  labels        text[] not null default '{}',
  erstellt_at   timestamptz not null default now(),
  unique (user_id, gmail_msg_id)
);
create index if not exists mails_user_datum on public.mails (user_id, datum desc);
create index if not exists mails_user_ungelesen on public.mails (user_id) where not gelesen;

alter table public.mails enable row level security;
-- Jede ID sieht nur ihre eigenen Mails — ausdrücklich OHNE Admin-Ausnahme (auch Admin sieht im Reiter nur den eingeloggten Login).
drop policy if exists "mails eigene lesen" on public.mails;
create policy "mails eigene lesen"   on public.mails for select using (auth.uid() = user_id);
drop policy if exists "mails eigene gelesen" on public.mails;
create policy "mails eigene gelesen" on public.mails for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- Kein insert/delete für Clients: schreiben tut nur Railway (service role). Ändern darf der Client nur die Spalte gelesen.
revoke all on public.mails from anon, authenticated;
grant select on public.mails to authenticated;
grant update (gelesen) on public.mails to authenticated;

create table if not exists public.mail_schluessel (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  token_sha256     text not null unique check (token_sha256 ~ '^[0-9a-f]{64}$'),   -- nur der Hash, nie der Klartext
  erstellt_at      timestamptz not null default now(),
  zuletzt_at       timestamptz,       -- letzte Meldung des Scripts (Railway)
  zuletzt_mail_at  timestamptz,       -- Datum der jüngsten angenommenen Mail (Railway)
  import_stand     jsonb              -- {fertig, gesendet} vom Erst-Import (Railway)
);

alter table public.mail_schluessel enable row level security;
drop policy if exists "mail_schluessel eigene lesen" on public.mail_schluessel;
create policy "mail_schluessel eigene lesen"   on public.mail_schluessel for select using (auth.uid() = user_id);
drop policy if exists "mail_schluessel eigene anlegen" on public.mail_schluessel;
create policy "mail_schluessel eigene anlegen" on public.mail_schluessel for insert with check (auth.uid() = user_id);
drop policy if exists "mail_schluessel eigene aendern" on public.mail_schluessel;
create policy "mail_schluessel eigene aendern" on public.mail_schluessel for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- „Neu verbinden" = neuer Hash (alter Schlüssel sofort ungültig) und Stand zurück; die Status-Spalten schreibt sonst nur Railway.
revoke all on public.mail_schluessel from anon, authenticated;
grant select on public.mail_schluessel to authenticated;
grant insert (user_id, token_sha256, erstellt_at, zuletzt_at, zuletzt_mail_at, import_stand) on public.mail_schluessel to authenticated;
grant update (token_sha256, erstellt_at, zuletzt_at, zuletzt_mail_at, import_stand) on public.mail_schluessel to authenticated;

-- Aufräumen nur auf Finns Wort (nicht automatisch):
-- delete from public.mails where datum < now() - interval '180 days';

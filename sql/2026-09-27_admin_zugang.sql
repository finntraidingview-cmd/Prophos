-- Admin-Zugang je ID (27.09.2026, Finn: „wenn Emin unter seiner ID auf Admin geht, einen
-- anderen Code als meinen eingibt, sodass er dann seine Finanzen sieht … nur seine eigenen").
-- Eine Zeile hier = diese ID hat im Admin einen EIGENEN Code und sieht dort nur sich selbst
-- (nur_eigene). Das Backend (_wd_login → _admin_nur_uid) liest die Tabelle mit dem
-- Service-Key und dreht für diese ID die Personen-Ausblendung um; das Frontend liest nur die
-- eigene Zeile für den Code. Schreiben kann nur der Service-Key — die ID selbst kann ihre
-- Zeile nicht löschen und sich so den vollen Admin zurückholen.
-- Bewusst keine E-Mail im Code (app.py/prophos.html liegen im Repo).

create table if not exists public.admin_zugang (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  code       text not null check (code ~ '^[0-9]{4,8}$'),
  nur_eigene boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.admin_zugang enable row level security;

drop policy if exists admin_zugang_eigene_lesen on public.admin_zugang;
create policy admin_zugang_eigene_lesen on public.admin_zugang
  for select to authenticated
  using (user_id = (select auth.uid()));

-- Emin: Zeile wird mit einem zufälligen Code direkt eingespielt — der Code steht bewusst
-- NICHT in dieser Datei (Repo). Muster:
-- insert into public.admin_zugang (user_id, code) values ('6cceb3f3-dc78-48ee-8668-26081da3e70f', '<PIN>')
--   on conflict (user_id) do update set code = excluded.code;

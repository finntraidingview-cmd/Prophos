-- ADMIN-GRUPPEN (08.10.2026, Finn ~22:45 Dubai: „Emin bekommt seine Freunde als eigene IDs bei sich unter Admin … Ich sage in
-- Zukunft, wenn eine neue ID reinkommt: ‚die bitte zu dem oder dem', dann kommt sie entweder zu Hermann Technologies oder zu dem
-- Menschen"; Nachtrag 23:00: „Bau in der Datenbank eine kleine Struktur, die für die Zukunft immer sehr clean und übersichtlich ist").
--
-- ┌─ SO ORDNEST DU EINE NEUE ID ZU (eine Zeile, <user_id> und Gruppenname einsetzen) ───────────────────────────────────────────────┐
-- │ update public.id_gruppe_mitglied set gruppe_id = (select id from public.id_gruppen where name = 'Emin'), seit = now()          │
-- │  where user_id = '<user_id>';                                                                                                   │
-- │ Nachsehen: select * from public.id_gruppen_uebersicht;                                                                          │
-- └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
-- Neue Logins landen per Trigger automatisch in „Hermann Technologies" (auch ohne Zeile zählen sie dort) — also immer nur das update.
-- Neue Gruppe: insert into public.id_gruppen (name, verwalter_user_id) values ('<Name>', '<user_id des Verwalters>');
-- Der Verwalter braucht zusätzlich eine admin_zugang-Zeile mit eigenem Code (sql/2026-09-27_admin_zugang.sql), sonst kommt er im
-- Frontend nicht über die Code-Sperre.
--
-- MODELL
--   id_gruppen          eine Zeile je Gruppe. verwalter_user_id null = Hermann Technologies (Finns Admins) — genau EINE solche Gruppe.
--   id_gruppe_mitglied  eine Zeile je ID (user_id = Primärschlüssel → jede ID genau einer Gruppe). Der Verwalter steht in seiner Gruppe.
--   id_gruppen_uebersicht  Gruppe · Verwalter · Mitglied · seit — nur Service-Key / SQL-Editor.
-- WIRKUNG (app.py admin_sicht_menge, prophos.html Admin):
--   Verwalter        volles Admin, aber nur mit seiner Gruppe (Backend-Filter + RLS der Wallets).
--   Mitglied einer Verwalter-Gruppe ohne eigenen Zugang: im Admin nur sich selbst (wie Emin bis .1380), nie die HT-Daten.
--   Hermann Technologies + IDs ohne Zeile: wie bisher alles; Finn bekommt im Admin-Kopf Chips je Gruppe (Name aus id_gruppen.name).
--   Fehlen die Tabellen (Datei nicht eingespielt), gibt es keine Gruppen — Backend und Frontend laufen wie vor den Gruppen.
-- Live-DB: spielt der Master ein. Keine echten IDs, Namen oder E-Mails in dieser Datei (Repo) — Platzhalter unten.

-- ── 1. Tabellen ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
create table if not exists public.id_gruppen (
  id                uuid primary key default gen_random_uuid(),
  name              text not null unique check (length(btrim(name)) between 1 and 60),
  -- ohne on-delete-Aktion: einen Verwalter löscht man erst, wenn seine Gruppe umgehängt ist (set null gäbe eine zweite HT-Gruppe)
  verwalter_user_id uuid unique references auth.users(id),
  angelegt_at       timestamptz not null default now(),
  notiz             text
);
-- genau eine Gruppe ohne Verwalter (= Hermann Technologies) — der Trigger unten und der HT-Filter verlassen sich darauf
create unique index if not exists id_gruppen_eine_ohne_verwalter on public.id_gruppen ((verwalter_user_id is null))
  where verwalter_user_id is null;

create table if not exists public.id_gruppe_mitglied (
  user_id   uuid primary key references auth.users(id) on delete cascade,
  gruppe_id uuid not null references public.id_gruppen(id) on delete restrict,
  seit      timestamptz not null default now(),
  notiz     text
);
create index if not exists id_gruppe_mitglied_gruppe_idx on public.id_gruppe_mitglied (gruppe_id);

-- ── 2. RLS: Schreiben nur Service-Key (keine insert/update/delete-Policy); Lesen nur die eigene Gruppe ────────────────────────────
alter table public.id_gruppen         enable row level security;
alter table public.id_gruppe_mitglied enable row level security;

-- Gruppen, die der Aufrufer verwaltet — security definer, damit die Policy von id_gruppe_mitglied nicht über die RLS von id_gruppen
-- läuft (keine Rekursion)
create or replace function public.id_gruppe_verwaltet()
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select g.id from public.id_gruppen g where g.verwalter_user_id = auth.uid();
$$;
revoke all on function public.id_gruppe_verwaltet() from public;
grant execute on function public.id_gruppe_verwaltet() to authenticated;

drop policy if exists id_gruppen_verwalter_lesen on public.id_gruppen;
create policy id_gruppen_verwalter_lesen on public.id_gruppen
  for select to authenticated
  using (verwalter_user_id = (select auth.uid()));

drop policy if exists id_gruppe_mitglied_lesen on public.id_gruppe_mitglied;
create policy id_gruppe_mitglied_lesen on public.id_gruppe_mitglied
  for select to authenticated
  using (user_id = (select auth.uid()) or gruppe_id in (select public.id_gruppe_verwaltet()));

-- ── 3. Neue IDs landen in Hermann Technologies (Trigger auf auth.users) ─────────────────────────────────────────────────────────
-- Nie die Registrierung blockieren: jeder Fehler hier wird geschluckt — ohne Zeile zählt die ID ohnehin als Hermann Technologies.
create or replace function public.id_gruppe_neu_ht()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  begin
    insert into public.id_gruppe_mitglied (user_id, gruppe_id)
    select new.id, g.id from public.id_gruppen g where g.verwalter_user_id is null
    on conflict (user_id) do nothing;
  exception when others then
    null;
  end;
  return new;
end;
$$;
revoke all on function public.id_gruppe_neu_ht() from public;

drop trigger if exists id_gruppe_neu_ht on auth.users;
create trigger id_gruppe_neu_ht after insert on auth.users
  for each row execute function public.id_gruppe_neu_ht();

-- ── 4. Übersicht zum schnellen Nachsehen (nur Service-Key / SQL-Editor) ─────────────────────────────────────────────────────────
-- Jede ID genau einmal, auch ohne Zeile (dann „Hermann Technologies (ohne Zeile)"). Namen aus user_metadata.name, sonst die ersten
-- 8 Zeichen der ID — bewusst keine E-Mail.
create or replace view public.id_gruppen_uebersicht as
select coalesce(g.name, 'Hermann Technologies (ohne Zeile)')                              as gruppe,
       case when g.verwalter_user_id is null then null
            else coalesce(nullif(v.raw_user_meta_data->>'name', ''), left(v.id::text, 8)) end as verwalter,
       coalesce(nullif(u.raw_user_meta_data->>'name', ''), left(u.id::text, 8))           as mitglied,
       u.id                                                                                as user_id,
       m.seit,
       m.notiz
  from auth.users u
  left join public.id_gruppe_mitglied m on m.user_id = u.id
  left join public.id_gruppen g        on g.id = m.gruppe_id
  left join auth.users v               on v.id = g.verwalter_user_id
 order by (g.verwalter_user_id is not null), 1, 3;
revoke all on public.id_gruppen_uebersicht from public, anon, authenticated;
grant select on public.id_gruppen_uebersicht to service_role;

-- ── 5. Meta Wallet: RLS auf die Gruppen-Menge erweitern ─────────────────────────────────────────────────────────────────────────
-- admin_nur_eigene() (sql/2026-09-27_admin_zugang_wallets.sql) heißt jetzt „eingeschränkt": admin_zugang nur_eigene ODER Verwalter
-- einer Gruppe ODER Mitglied einer Verwalter-Gruppe — dieselbe Regel wie app.py admin_sicht_menge. Für alle anderen (HT) bleibt es
-- exakt wie bisher (die permissiven Policies bleiben stehen). wallet_labels + kasse_entries bleiben für Eingeschränkte gesperrt (HT-weit).
create or replace function public.admin_nur_eigene()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.admin_zugang z where z.user_id = auth.uid() and z.nur_eigene)
      or exists (select 1 from public.id_gruppen g where g.verwalter_user_id = auth.uid())
      or exists (select 1 from public.id_gruppe_mitglied m
                   join public.id_gruppen g on g.id = m.gruppe_id
                  where m.user_id = auth.uid() and g.verwalter_user_id is not null);
$$;
revoke all on function public.admin_nur_eigene() from public;
grant execute on function public.admin_nur_eigene() to authenticated;

-- sichtbare IDs eines Eingeschränkten: er selbst + die Mitglieder der Gruppen, die er verwaltet
create or replace function public.admin_sichtbare_ids()
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select auth.uid()
  union
  select m.user_id from public.id_gruppe_mitglied m
    join public.id_gruppen g on g.id = m.gruppe_id
   where g.verwalter_user_id = auth.uid();
$$;
revoke all on function public.admin_sichtbare_ids() from public;
grant execute on function public.admin_sichtbare_ids() to authenticated;

drop policy if exists nur_eigene_wallets on public.id_wallets;
create policy nur_eigene_wallets on public.id_wallets as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene())
         or person_uid in (select s::text from public.admin_sichtbare_ids() s))
  with check (not (select public.admin_nur_eigene())
         or person_uid in (select s::text from public.admin_sichtbare_ids() s));

drop policy if exists nur_eigene_snapshots on public.wallet_snapshots;
create policy nur_eigene_snapshots on public.wallet_snapshots as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w
                           where w.person_uid in (select s::text from public.admin_sichtbare_ids() s)))
  with check (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w
                           where w.person_uid in (select s::text from public.admin_sichtbare_ids() s)));

drop policy if exists nur_eigene_wallet_tx on public.wallet_tx;
create policy nur_eigene_wallet_tx on public.wallet_tx as restrictive
  for all to authenticated
  using (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w
                           where w.person_uid in (select s::text from public.admin_sichtbare_ids() s)))
  with check (not (select public.admin_nur_eigene())
         or wallet_id in (select w.id from public.id_wallets w
                           where w.person_uid in (select s::text from public.admin_sichtbare_ids() s)));

-- ── 6. SEED — Platzhalter, der Master setzt beim Einspielen die zwei user_ids ein (nie ins Repo) ────────────────────────────────
--   :'emin' = user_id des Verwalters (hat die admin_zugang-Zeile mit nur_eigene = true)
--   :'amir' = user_id des neuen Mitglieds (Login seit 08.10.2026)
-- psql: \set emin '<uuid>' und \set amir '<uuid>' vor dem Lauf; im SQL-Editor / execute_sql jedes :'emin' bzw. :'amir' durch
-- '<uuid>' ersetzen. Nachschlagen z. B.: select id, raw_user_meta_data->>'name' from auth.users order by created_at desc limit 10;
insert into public.id_gruppen (name, verwalter_user_id, notiz)
values ('Hermann Technologies', null, 'Finns Admins — jede ID ohne andere Gruppe')
on conflict (name) do nothing;

-- Gruppe „Emin" nur, wenn der Verwalter wirklich eine admin_zugang-Zeile mit nur_eigene hat (sonst käme er nicht in den Admin)
insert into public.id_gruppen (name, verwalter_user_id, notiz)
select 'Emin', :'emin'::uuid, 'Verwalter mit eigenem Admin-Code (admin_zugang)'
 where exists (select 1 from public.admin_zugang z where z.user_id = :'emin'::uuid and z.nur_eigene)
on conflict (name) do update set verwalter_user_id = excluded.verwalter_user_id;

-- Hermann Technologies: alle bestehenden IDs außer Emin und Amir
insert into public.id_gruppe_mitglied (user_id, gruppe_id)
select u.id, g.id
  from auth.users u
  cross join public.id_gruppen g
 where g.name = 'Hermann Technologies'
   and u.id not in (:'emin'::uuid, :'amir'::uuid)
on conflict (user_id) do nothing;

-- Emin: Verwalter selbst + Amir
insert into public.id_gruppe_mitglied (user_id, gruppe_id)
select x.user_id, g.id
  from (values (:'emin'::uuid), (:'amir'::uuid)) as x(user_id)
  cross join public.id_gruppen g
 where g.name = 'Emin'
on conflict (user_id) do update set gruppe_id = excluded.gruppe_id, seit = now();

-- ── 7. Kontrolle nach dem Einspielen ─────────────────────────────────────────────────────────────────────────────────────────────
-- select * from public.id_gruppen_uebersicht;                       -- jede ID genau einmal, Emin-Gruppe = 2 Zeilen
-- select name, verwalter_user_id is null as ht from public.id_gruppen;
-- Danach dauert es bis zu 60 s, bis das Backend die Gruppen kennt (admin_gruppen_daten, Cache).

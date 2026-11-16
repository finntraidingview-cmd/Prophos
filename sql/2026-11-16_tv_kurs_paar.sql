-- SB4 (16.11.2026, Supabase-Rechnung 232 $, Befund SB1): Realtime ≈ 99 % = tv_kurse. Der Liefer-PC (Reader-Direktfeed über
-- Railway /reader-kurs, Tab-Brücke als Reserve) upsertet NQ und MNQ meist in EINEM Aufruf, das sind aber ZWEI Zeilen-Änderungen →
-- zwei Realtime-Nachrichten je Abonnent. Gemessen 16.11. 09–11 UTC: 0,74 Upserts/s, 1,13 Zeilen-Änderungen/s, ~8 Abonnenten
-- ≈ 780.000 Nachrichten/Tag.
-- NQ = MNQ ist KEIN Ausweg: 725 Minuten verglichen, Schlusskurs nur in 49 gleich, im Mittel 1,3 Punkte, max. 19,5 auseinander.
--
-- Lösung ohne Änderung an Reader, Railway oder Tab-Brücke: ein Statement-Trigger fasst jedes tv_kurse-Upsert zu EINER Zeile je
-- PC in tv_kurs_paar zusammen (beide Wurzeln als jsonb = die tv_kurse-Zeile 1:1, `geaendert` = welche Wurzeln dieses Upsert
-- geschrieben hat). Die Tabs (markt-live, prophos.html mklRealtimeStart) abonnieren tv_kurs_paar statt tv_kurse → eine Nachricht
-- je Upsert statt je Zeile (≈ −35 %). tv_kurse bleibt Quelle für alles Lesen per REST (Klick-Puffer, Polling, Radar, Railway).
-- Alte Tabs (vor dem Neuladen) hören weiter tv_kurse — darum bleibt tv_kurse vorerst in der Publication. Wenn
-- realtime.subscription keine tv_kurse-Abos mehr zeigt, kann es raus (Schritt 2 unten, auskommentiert, Master entscheidet).
--
-- Fail-safe: der Trigger fängt jeden eigenen Fehler ab (RAISE WARNING) — das tv_kurse-Upsert des Feeds scheitert nie an ihm
-- (Finn: „Reader-Kurs darf nicht leiden“). Idempotent.

create table if not exists public.tv_kurs_paar (
  id          text primary key,            -- = tv_kurse.pc_name
  pc_name     text not null,
  nq          jsonb,                       -- letzte tv_kurse-Zeile `${pc}:NQ` (to_jsonb, alle Spalten)
  mnq         jsonb,                       -- letzte tv_kurse-Zeile `${pc}:MNQ`
  geaendert   text[] not null default '{}',-- Wurzeln, die das letzte Upsert geschrieben hat (nur die wertet der Tab aus)
  updated_at  timestamptz not null default now()
);
comment on table public.tv_kurs_paar is
  'SB4 16.11.2026: Realtime-Spiegel von tv_kurse, eine Zeile je Liefer-PC mit NQ + MNQ — eine Realtime-Nachricht je Upsert statt je Wurzel. Schreibt nur der Trigger tv_kurs_paar_sync.';

alter table public.tv_kurs_paar enable row level security;
drop policy if exists "tv_kurs_paar read" on public.tv_kurs_paar;
create policy "tv_kurs_paar read" on public.tv_kurs_paar for select to authenticated using (true);   -- wie "tv_kurse read"
revoke all on public.tv_kurs_paar from public, anon;
grant select on public.tv_kurs_paar to authenticated;

create or replace function public.tv_kurs_paar_sync()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  begin
    insert into public.tv_kurs_paar as p (id, pc_name, nq, mnq, geaendert, updated_at)
    select n.pc_name, n.pc_name,
           (jsonb_object_agg(n.wurzel, to_jsonb(n)) -> 'NQ'),
           (jsonb_object_agg(n.wurzel, to_jsonb(n)) -> 'MNQ'),
           array_agg(distinct n.wurzel order by n.wurzel),
           max(n.updated_at)
    from neu n
    where n.wurzel in ('NQ', 'MNQ') and coalesce(n.pc_name, '') <> ''
    group by n.pc_name
    on conflict (id) do update
      set nq         = coalesce(excluded.nq,  p.nq),
          mnq        = coalesce(excluded.mnq, p.mnq),
          geaendert  = excluded.geaendert,
          updated_at = greatest(excluded.updated_at, p.updated_at);
  exception when others then
    raise warning 'tv_kurs_paar_sync: % (%)', sqlerrm, sqlstate;   -- nie das Kurs-Upsert kippen
  end;
  return null;
end
$$;
revoke all on function public.tv_kurs_paar_sync() from public, anon, authenticated;

-- Upsert (INSERT … ON CONFLICT DO UPDATE) feuert beide Statement-Trigger, jeder mit seiner eigenen Übergangstabelle.
drop trigger if exists tv_kurs_paar_ins on public.tv_kurse;
create trigger tv_kurs_paar_ins after insert on public.tv_kurse
  referencing new table as neu for each statement execute function public.tv_kurs_paar_sync();
drop trigger if exists tv_kurs_paar_upd on public.tv_kurse;
create trigger tv_kurs_paar_upd after update on public.tv_kurse
  referencing new table as neu for each statement execute function public.tv_kurs_paar_sync();

-- Startbestand aus den aktuellen tv_kurse-Zeilen (sonst fehlt eine Wurzel bis zu ihrem nächsten Upsert)
insert into public.tv_kurs_paar as p (id, pc_name, nq, mnq, geaendert, updated_at)
select k.pc_name, k.pc_name,
       (jsonb_object_agg(k.wurzel, to_jsonb(k)) -> 'NQ'),
       (jsonb_object_agg(k.wurzel, to_jsonb(k)) -> 'MNQ'),
       '{}', max(k.updated_at)
from public.tv_kurse k
where k.wurzel in ('NQ', 'MNQ') and k.id like '%:%' and coalesce(k.pc_name, '') <> ''
group by k.pc_name
on conflict (id) do nothing;

do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'tv_kurs_paar') then
    alter publication supabase_realtime add table public.tv_kurs_paar;
  end if;
end $$;

notify pgrst, 'reload schema';

-- Schritt 2 (SPÄTER, erst wenn `select count(*) from realtime.subscription where entity = 'public.tv_kurse'::regclass` = 0):
-- alter publication supabase_realtime drop table public.tv_kurse;

-- 2026-11-26 — KP3 Vorrat-Ziele und Kauf-Größe je Unternehmen (Master 25./26.11.2026, Finn: „Kaufliste/Musterportfolio müssen HT-IDs und Emin-IDs
-- unterscheiden, z. B. kauft Emin immer nur 50k-Konten“). Konstrukt vom Master abgenommen, Variante (b), Emin-Werte von Finn (Master 26.11.2026).
--
-- Neue Tabelle vorrat_ziele_gruppe = eigene Ziel-Zeilen je Gruppe (id_gruppen.id) und Firma, gleiche Felder wie vorrat_ziele. Hat eine Gruppe KEINE Zeile
-- für eine Firma, gilt für ihre IDs weiter vorrat_ziele (HT hat keine Zeilen → bitgleich wie bisher). Lesen/Schreiben nur über Railway (Service-Key):
-- RLS an, keine Policy für anon/authenticated, Rechte entzogen (wie vorrat_ziele); backup_reader darf lesen (Sicherung).
-- Seed Emin (Gruppe mit Verwalter UND Gruppen-Planer = die Gruppe „Emin“; über die Daten bestimmt, keine feste ID) — Finns Werte (Master 26.11.2026):
--   Lucid Trading       Ziel +5.000 bis +10.000 $ Winning Days, Kauf 50k
--   FundedNext Futures  Ziel +5.000 bis +10.000 $ Winning Days, Kauf 50k
-- Alles andere wie HT, also KEINE eigene Zeile: CFD (Ziele für alle schon in vorrat_ziele, Kauf 100k), Tradeify/Topstep/Apex (Emin hat dort keine IDs),
-- FTMO Futures (1 Konto Winning Days bei +5.000, Kauf 50k Pro — HT hat genau das). Art, Typen und Reihe der Zeilen aus vorrat_ziele. Nur Zeilen, die
-- es noch nicht gibt → wiederholbar, überschreibt nie Werte, die Emin/Finn später ändern.
-- NICHT EINGESPIELT — Ausführen nur auf Finns/Masters Wort, nicht von einem Slave. Rückbau: drop table public.vorrat_ziele_gruppe; (der Lauf fällt
-- ohne Tabelle auf vorrat_ziele zurück — PostgREST 404 wird abgefangen).

begin;

create table if not exists public.vorrat_ziele_gruppe (
  gruppe_id    uuid        not null references public.id_gruppen(id) on delete cascade,
  firma        text        not null,
  art          text        not null check (art in ('plus_ueber_start', 'groessen_summe', 'stueck')),
  typen        text[]      not null default '{}',
  von          numeric,
  bis          numeric,
  groessen     jsonb,
  kauf_einheit text,
  kauf_groesse numeric     check (kauf_groesse is null or kauf_groesse > 0),
  reihe        smallint,
  updated_at   timestamptz not null default now(),
  updated_by   uuid,
  primary key (gruppe_id, firma)
);

alter table public.vorrat_ziele_gruppe enable row level security;
revoke all on public.vorrat_ziele_gruppe from anon, authenticated;
do $backup$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.vorrat_ziele_gruppe to backup_reader';
    if not exists (select 1 from pg_policy where polrelid = 'public.vorrat_ziele_gruppe'::regclass and polname = 'backup_reader_select') then
      execute 'create policy backup_reader_select on public.vorrat_ziele_gruppe for select to backup_reader using (true)';
    end if;
  end if;
end $backup$;

-- Seed Emin: Gruppen mit Verwalter und auto_plan_gruppe-Zeile (heute genau „Emin“), nur Lucid + FundedNext Futures (Finns Werte)
insert into public.vorrat_ziele_gruppe (gruppe_id, firma, art, typen, von, bis, groessen, kauf_einheit, kauf_groesse, reihe)
select g.id, z.firma, z.art, z.typen, w.von, w.bis, null, '50k', 50000, z.reihe
  from public.vorrat_ziele z
  join (values ('Lucid Trading', 5000::numeric, 10000::numeric), ('FundedNext Futures', 5000, 10000)) as w(firma, von, bis) on w.firma = z.firma
  join public.id_gruppen g on g.verwalter_user_id is not null
                          and exists (select 1 from public.auto_plan_gruppe apg where apg.gruppe_id = g.id)
on conflict (gruppe_id, firma) do nothing;

commit;

-- Prüfen (nur lesen):
--   select g.name, z.firma, z.art, z.von, z.bis, z.kauf_einheit, z.kauf_groesse from public.vorrat_ziele_gruppe z join public.id_gruppen g on g.id = z.gruppe_id
--    order by g.name, z.reihe;   -- Stand 26.11.: 2 Zeilen Emin — Lucid Trading + FundedNext Futures, plus_ueber_start 5.000–10.000, 50k

-- ============================================================================
-- Prophos: KP2d Kaufliste „Später" (25.11.2026) — NICHT eingespielt (Prüfer-Pflicht)
--
-- Finn zu „Erledigt": der Knopf heißt für ihn „ich will gerade nicht kaufen" (z. B. Tradeify/The5ers, weil er bald ins Live-Programm kommt)
-- → „weg, komm in 7 Tagen wieder". Bewusst NICHT vorrat_bestellt: das zieht die Anzeige als „schon gekauft, unterwegs" von der Kaufzahl ab
-- (vorrat_anzeige_n). „Später" hat KEINE Rechenwirkung — die Zeilen sind nur ausgeblendet, bis „bis" erreicht ist oder Rückgängig.
--
--   kaufliste_spaeter   je Klick eine Zeile: ID × Firma, wie viele Konten der Zelle ausgeblendet sind, bis wann; weg_at = Rückgängig.
--
-- RLS an, keine Policy für Logins, Rechte anon/authenticated entzogen — nur der Service-Key (Railway, kaufliste_app.py). Idempotent.
-- ============================================================================

create table if not exists public.kaufliste_spaeter (
  id       bigint generated always as identity primary key,
  user_id  uuid not null,
  firma    text not null,
  anzahl   int  not null check (anzahl between 1 and 20),
  tage     int  not null check (tage between 1 and 60),
  bis      timestamptz not null,
  von      uuid,
  at       timestamptz not null default now(),
  weg_at   timestamptz
);
create index if not exists kaufliste_spaeter_offen_idx on public.kaufliste_spaeter (user_id, firma, bis) where weg_at is null;

alter table public.kaufliste_spaeter enable row level security;
revoke all on public.kaufliste_spaeter from anon, authenticated;
grant all on public.kaufliste_spaeter to service_role;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.kaufliste_spaeter to backup_reader';
    execute 'drop policy if exists backup_reader_select on public.kaufliste_spaeter';
    execute 'create policy backup_reader_select on public.kaufliste_spaeter for select to backup_reader using (true)';
  end if;
end $$;

-- Kontrolle:
-- select relrowsecurity from pg_class where oid = 'public.kaufliste_spaeter'::regclass;
-- select * from kaufliste_spaeter where weg_at is null and bis > now() order by bis;

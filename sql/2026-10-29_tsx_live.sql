-- TOPSTEPX-HAND-POSITIONEN FÜR DEN RICHTUNGSSCHUTZ (29.10.2026, Lücke D aus dem Richtungsschutz-Audit, Finn: „auf gar keinen Fall interner
-- Hedge"). Hand-Positionen in TopstepX ohne Plan waren für fremd_positionen unsichtbar — fp_tick (app.py) las nur mt5_live und echoplus_live.
-- Das TopstepX-Auge (Userscript im Puls-Chrome) meldet dem Panel Konto + Positionen live; der PC-Tab (prophos.html tsxLiveTick) schreibt sie
-- wie die TV-Brücke nach echoplus_live in EINE Zeile je PC hierher. fp_tick liest frische Zeilen (≤ 90 s, positionen_ok) als quelle 'tsx'
-- in fremd_positionen — damit sperren prophos_gegenhedge_konflikt / prophos_fremd_konflikte auch gegen TopstepX-Hand-Trades (die Funktionen
-- unterscheiden keine Quelle).
-- positionen_ok nur mit Beweis (Stand ≤ 10 s, nicht ausgeloggt, volle Kontonummer, Liste zu, flach bewiesen — flach_folge ≥ 3 über ≥ 200 ms —
-- oder Position gelesen; zwei gleiche Lesungen ≥ 3 s auseinander, Puls nicht unterwegs). vollstaendig: nur dann schließt fp_tick (weg_at).
-- BEKANNTE GRENZE DES RIEGELS (Gegenlesung 29.10.2026, gilt für mt5/tv/tsx gleich): prophos_gegenhedge_konflikt zählt eine Fremd-Position
-- nur in den ersten 90 s ab seit — eine länger offene Hand-Position sperrt eine Gegenrichtung danach nicht mehr (eigener SQL-Schritt, offen).
-- GRENZE: das Auge sieht nur das GERADE GEWÄHLTE TopstepX-Konto — andere Konten desselben Logins bleiben unsichtbar (wie bei TradingView).
-- Rechte wie echoplus_live (eingeloggte Tabs lesen/schreiben, Backup-Leser liest). Einspielen: Master nach Prüfer-OK. Idempotent.
--
-- RÜCKNAHME:
--   drop table if exists public.tsx_live;
--   (fremd_positionen-Zeilen mit quelle 'tsx' bleiben stehen und verfallen über weg_at bzw. die 3-min-Aktiv-Grenze — bei Bedarf:
--    update public.fremd_positionen set weg_at = now() where quelle = 'tsx' and weg_at is null;)

create table if not exists public.tsx_live (
  id text primary key,                         -- PC-Kennung (pc-xxxxxx)
  pc_name text default ''::text,
  konto text,                                  -- konto.kontonr des Auges (volle Kennung)
  abgekuerzt boolean,
  positionen jsonb default '[]'::jsonb,        -- [{symbol, seite: buy|sell, menge, avg}] — höchstens 10
  positionen_ok boolean,
  vollstaendig boolean,                        -- flach bewiesen oder alle Positionen aus der Positions-Tabelle — nur dann darf fp_tick schließen
  flach boolean,
  ausgeloggt boolean,
  script text,                                 -- Version des Auges
  stand_ts timestamptz,                        -- Zeit der Lesung (Panel-Uhr minus alter_s)
  updated_at timestamptz default now()
);

alter table public.tsx_live enable row level security;

drop policy if exists "tsx_live read" on public.tsx_live;
create policy "tsx_live read" on public.tsx_live for select to authenticated using (true);
drop policy if exists "tsx_live insert" on public.tsx_live;
create policy "tsx_live insert" on public.tsx_live for insert to authenticated with check (true);
drop policy if exists "tsx_live update" on public.tsx_live;
create policy "tsx_live update" on public.tsx_live for update to authenticated using (true) with check (true);
drop policy if exists "tsx_live delete" on public.tsx_live;
create policy "tsx_live delete" on public.tsx_live for delete to authenticated using (true);

do $$ begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'drop policy if exists backup_reader_select on public.tsx_live';
    execute 'create policy backup_reader_select on public.tsx_live for select to backup_reader using (true)';
    execute 'grant select on public.tsx_live to backup_reader';
  end if;
end $$;

grant select, insert, update, delete on public.tsx_live to authenticated;

-- ============================================================================
-- Prophos/Echo: echo_notfall — die Notfall-SL/TP-Einstellungen, persistent in
-- der DB
--
-- Finns Ansage (27.08.2026, direkt nach dem Notfall-SL/TP-Bau, c06a888):
-- „wollen wir die 110% etc als sql gleich speichern, dass es da nie Problem
-- später gibt — wäre mir wichtig." Ohne DB lebten die Werte nur in den
-- config*.json der PCs — ein neu provisionierter PC, eine gelöschte Config
-- oder eine frische Vorlage fiele still auf die Code-Defaults zurück.
--
-- EINE globale Zeile (key = 'global') statt einer pro PC: die Notfall-Werte
-- sind eine Policy der ganzen Flotte, kein PC-Merkmal wie das Hedge-Konto
-- in echo_hedge. So heilt der Guard auch PCs, die es heute noch gar nicht
-- gibt. Das Speichern auf einer Echo-Karte schreibt hierher; die
-- Selbstheilung im Frontend (echoNotfallGuard, Muster echoHedgeGuard)
-- vergleicht bei jedem Poll die Configs des PCs mit diesem Wert und stellt
-- Abweichungen automatisch per save?file= zurück. Tabelle fehlt oder leer
-- → Guard bleibt still (additiv, blockt nie).
--
-- Geteilt wie echo_hedge/mt5_live: die Flotte ist EINE Operation, jeder
-- eingeloggte User liest und schreibt (die PCs laufen unter verschiedenen
-- Profilen — wer auch immer dort eingeloggt ist, darf heilen).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.echo_notfall (
  key                       text primary key default 'global',
  notfall_faktor            numeric not null,
  notfall_puffer_min_punkte numeric not null,
  updated_at                timestamptz not null default now()
);

alter table public.echo_notfall enable row level security;

drop policy if exists "echo_notfall read"   on public.echo_notfall;
drop policy if exists "echo_notfall insert" on public.echo_notfall;
drop policy if exists "echo_notfall update" on public.echo_notfall;

create policy "echo_notfall read"   on public.echo_notfall for select to authenticated using (true);
create policy "echo_notfall insert" on public.echo_notfall for insert to authenticated with check (true);
create policy "echo_notfall update" on public.echo_notfall for update to authenticated using (true) with check (true);

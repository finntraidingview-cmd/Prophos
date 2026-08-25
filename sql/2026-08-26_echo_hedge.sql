-- ============================================================================
-- Prophos/Echo: echo_hedge — das Hedge-Konto jedes PCs, persistent in der DB
--
-- Finns Bug (25.08.2026 abends): nach „Account hinzufügen" erbte die neue
-- Config ein altes Hedge-Konto aus der PC-Vorlage — die Flotten-Prüfung brach
-- ab („hedge_expected_login unterscheiden sich"), der Copier stand in der
-- Neustart-Schleife, und der 🎯-Chip-Wert war praktisch „weg".
--
-- Finns Ansage (25.08.2026): „den Chip in die Datenbank packen, dass jeder
-- immer seinen aktuellen Chip reinmacht — dass das nie wieder passiert."
--
-- Eine Zeile pro PC (pc_name = mt5FleetPcId aus dem Frontend). Der 🎯-Chip
-- schreibt beim Umstellen hierher; die Selbstheilung im Frontend
-- (echoHedgeGuard) vergleicht bei jedem Poll die Configs des PCs mit diesem
-- Wert und stellt Abweichungen automatisch per /api/set-hedge zurück.
-- Zusätzlich erbt die Provisionierung seit VERSION .119 die Hedge-Felder aus
-- der lebenden Flotte statt aus der Vorlage — doppelter Boden.
--
-- Geteilt wie mt5_live/kasse_entries: die Flotte ist EINE Operation, jeder
-- eingeloggte User liest und schreibt (die PCs laufen unter verschiedenen
-- Profilen — Jacob stellt den Chip, Finns Profil darf ihn genauso heilen).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.echo_hedge (
  pc_name     text primary key,
  hedge_login text not null,
  updated_at  timestamptz not null default now()
);

alter table public.echo_hedge enable row level security;

drop policy if exists "echo_hedge read"   on public.echo_hedge;
drop policy if exists "echo_hedge insert" on public.echo_hedge;
drop policy if exists "echo_hedge update" on public.echo_hedge;

create policy "echo_hedge read"   on public.echo_hedge for select to authenticated using (true);
create policy "echo_hedge insert" on public.echo_hedge for insert to authenticated with check (true);
create policy "echo_hedge update" on public.echo_hedge for update to authenticated using (true) with check (true);

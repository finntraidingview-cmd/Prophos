-- ============================================================================
-- Prophos: mt5_live — Fleet-Live-Stand aller MT5-Copier-Instanzen
--
-- Finns Fleet-Feature (18.08.2026): jede ID läuft auf ihrem eigenen PC, jeder
-- PC sieht nur die eigenen Trades. Diese Tabelle ist der Cloud-Treffpunkt:
-- jeder PC mit lokalem Copier upsertet alle ~5s eine Zeile PRO INSTANZ
-- (Master-Login, Positionen, Hedges, Balances, Note) — die Live-Trades-View
-- liest ALLE Zeilen und zeigt die ganze Flotte, egal an welchem PC.
--
-- Bewusst NICHT nach user_id getrennt (Muster kasse_entries): die Flotte ist
-- EINE Operation, auf den PCs sind verschiedene Prophos-Profile eingeloggt
-- (Finn, Jacob, …) — jeder authentifizierte User sieht und schreibt alles.
--
-- Frische-Beweis: updated_at. Zeilen älter ~20s zeigt das Frontend ausgegraut
-- ("zuletzt vor Xs"), älter 10min gar nicht — nie alte Daten als live.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.mt5_live (
  id           text primary key,            -- <pc_id>:<config-datei> (pc_id = localStorage-Kennung des PCs)
  pc_name      text not null default '',
  config_file  text not null default '',
  instance     text not null default '',    -- Anzeigename (aus dem Config-Dateinamen)
  master_login text not null default '',
  hedge_login  text not null default '',
  alive        boolean not null default false,
  status       jsonb not null default '{}'::jsonb,  -- note, mode, multiplier, master_positions, hedges, Balances/Equities
  updated_at   timestamptz not null default now()
);

alter table public.mt5_live enable row level security;

drop policy if exists "mt5_live read"   on public.mt5_live;
drop policy if exists "mt5_live insert" on public.mt5_live;
drop policy if exists "mt5_live update" on public.mt5_live;
drop policy if exists "mt5_live delete" on public.mt5_live;

-- Alle authentifizierten Prophos-User teilen sich den Fleet-Stand (profilübergreifend).
create policy "mt5_live read"   on public.mt5_live for select to authenticated using (true);
create policy "mt5_live insert" on public.mt5_live for insert to authenticated with check (true);
create policy "mt5_live update" on public.mt5_live for update to authenticated using (true) with check (true);
create policy "mt5_live delete" on public.mt5_live for delete to authenticated using (true);

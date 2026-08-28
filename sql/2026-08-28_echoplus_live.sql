-- ============================================================================
-- Prophos: echoplus_live — Cloud-Stand des TradingView-Readers (Echo +)
--
-- Echo + (28.08.2026): der Browser-Reader (tv-reader/) liest die Master-
-- Positionen aus TradingView und hält sie lokal (reader-server.py, Port 8790).
-- Diese Tabelle ist der Cloud-Treffpunkt dafür — dasselbe Prinzip wie mt5_live
-- beim Flotten-Puls: der Prophos-Tab des Geräts, auf dem der Reader läuft,
-- upsertet alle ~5s EINE Zeile pro Gerät. Jedes andere Gerät (Handy, Mac)
-- sieht damit in der Echo-+-View live, was der Reader sieht.
--
-- Fernschalter: soll_an ist der WUNSCH (aus Prophos geschaltet, von überall),
-- an ist der IST-Zustand (vom Gerät gemeldet). Der Brücken-Tab setzt den
-- Wunsch beim lokalen reader-server durch und meldet den Ist zurück — soll_an
-- wird bewusst NIE gelöscht (sticky), damit es keine Race-Fenster gibt: die
-- Zeile IST der Schalter, der Tab setzt ihn idempotent durch.
--
-- Bewusst NICHT nach user_id getrennt (Muster mt5_live/kasse): die Flotte ist
-- EINE Operation — jeder authentifizierte Prophos-User sieht und schaltet alles.
--
-- Frische-Beweis: updated_at (Push-Zeit) + reader_ts (Zeit der letzten echten
-- Reader-Daten, ms). Das Frontend zeigt alte Zeilen ausgegraut, nie als live.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.echoplus_live (
  id         text primary key,                    -- pc_id (localStorage-Kennung, wie mt5_live)
  pc_name    text not null default '',
  an         boolean not null default true,       -- Ist-Zustand des Readers (vom Gerät gemeldet)
  soll_an    boolean,                             -- Fernschalter-Wunsch (null = nie geschaltet)
  positionen jsonb not null default '[]'::jsonb,  -- [{symbol, seite, menge, einstieg, sl, tp, pnl}]
  reader_ts  bigint not null default 0,           -- ts (ms) der letzten Daten vom Userscript
  updated_at timestamptz not null default now()
);

alter table public.echoplus_live enable row level security;

drop policy if exists "echoplus_live read"   on public.echoplus_live;
drop policy if exists "echoplus_live insert" on public.echoplus_live;
drop policy if exists "echoplus_live update" on public.echoplus_live;
drop policy if exists "echoplus_live delete" on public.echoplus_live;

-- Alle authentifizierten Prophos-User teilen sich den Stand (profilübergreifend).
create policy "echoplus_live read"   on public.echoplus_live for select to authenticated using (true);
create policy "echoplus_live insert" on public.echoplus_live for insert to authenticated with check (true);
create policy "echoplus_live update" on public.echoplus_live for update to authenticated using (true) with check (true);
create policy "echoplus_live delete" on public.echoplus_live for delete to authenticated using (true);

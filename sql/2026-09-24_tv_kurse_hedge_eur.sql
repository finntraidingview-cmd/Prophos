-- ============================================================================
-- Prophos: Winning Days gegenhedgen auf Fusion (24.09.2026 abends)
--
-- Finn: „Ich will von Duplikum 100 % wegkommen. Auf einem PC, der 24/7 läuft,
-- liest der Reader die aktuellen NQ-/MNQ-Punkte. Wird ein Winning Day per Puls
-- platziert, merkt sich Prophos, bei welcher Punktzahl der Take Profit liegt,
-- öffnet direkt danach auf Fusion Markets die Gegen-Order im Verhältnis, und
-- sobald NQ den TP (plus 2–3 Punkte) erreicht, wird die Fusion-Order geschlossen."
--
-- 1) tv_kurse — Cloud-Treffpunkt für den Live-Kurs aus TradingView.
--    Dasselbe Muster wie echoplus_live: der Prophos-Tab des PCs, auf dem der
--    Reader läuft, upsertet alle ~5 s EINE Zeile pro Gerät (id = pc_id). Quelle
--    ist der Tab-Titel („NQZ2026 30,448.25 ▼ −1.03%"), den das Userscript ohnehin
--    mitschickt — er hängt an keinem Seitenelement, das TradingView umbenennen
--    könnte. Wer den Kurs braucht, nimmt die JÜNGSTE Zeile über alle PCs.
--    Nicht nach user_id getrennt (Muster mt5_live/echoplus_live): die Flotte ist
--    EINE Operation. Frische-Beweis: reader_ts (Browser-Zeit des Titels) +
--    updated_at (Push-Zeit) — nie einen alten Kurs als live behaupten.
--
-- 2) trade_plans.hedge_eur — Betrag in €, den die Fusion-Gegenposition eines
--    V2-Plans trägt (Staffel aus dem Winning-Day-Farmer oder von Hand im Order-
--    Popup). NULL = kein Gegenhedge. Der Rest des Hedges (Ticket, Lots, TP-Level
--    in NQ-Punkten, Ergebnis) liegt in mt5_baseline.hedge — wie live/final/tv.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.tv_kurse (
  id         text primary key,                    -- pc_id (localStorage-Kennung, wie echoplus_live)
  pc_name    text not null default '',
  symbol     text not null default '',            -- wie im Titel: NQZ2026 / MNQZ2026 / NQ1!
  wurzel     text not null default '',            -- NQ / MNQ (Symbolwurzel ohne Monat)
  preis      numeric,                             -- geparster Kurs, NULL wenn der Titel nicht lesbar war
  text       text not null default '',            -- Roh-Text aus dem Titel („30,448.25")
  sichtbar   boolean not null default true,       -- Tab sichtbar? (verdeckter Tab tickt gedrosselt)
  reader_ts  bigint not null default 0,           -- ts (ms) des Userscript-Ticks, aus dem der Titel stammt
  updated_at timestamptz not null default now()
);

alter table public.tv_kurse enable row level security;

drop policy if exists "tv_kurse read"   on public.tv_kurse;
drop policy if exists "tv_kurse insert" on public.tv_kurse;
drop policy if exists "tv_kurse update" on public.tv_kurse;
drop policy if exists "tv_kurse delete" on public.tv_kurse;

create policy "tv_kurse read"   on public.tv_kurse for select to authenticated using (true);
create policy "tv_kurse insert" on public.tv_kurse for insert to authenticated with check (true);
create policy "tv_kurse update" on public.tv_kurse for update to authenticated using (true) with check (true);
create policy "tv_kurse delete" on public.tv_kurse for delete to authenticated using (true);

alter table public.trade_plans add column if not exists hedge_eur numeric;
comment on column public.trade_plans.hedge_eur is
  'Fusion-Gegenhedge in € (Winning Days, 24.09.2026): NULL = kein Hedge. Details in mt5_baseline.hedge.';

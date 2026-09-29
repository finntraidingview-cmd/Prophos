-- 2026-09-29: Puls-Ergebnisse als Sicherheitsnetz (Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24, pc-usq1i6).
-- Der neue Puls (Puls-Chrome) platzierte BUY 1 MNQZ6 @ 30606 sauber — die Antwort erreichte den Prophos-Tab aber nie: kein
-- order_signale-Eintrag, Plan blieb „Geplant", Position in TradingView offen und für Prophos unsichtbar. Ab jetzt meldet der Bot
-- jede scharfe Order und jedes Schließen ZUSÄTZLICH selbst (Railway POST /puls-ergebnis/<pc_id>, Service-Key): einmal direkt
-- nach dem Senden-Klick (stufe 'geklickt') und am Ende ('ende'). Der PC-Tab des Plan-Besitzers übernimmt ein Ergebnis, das nie
-- verarbeitet wurde (Plan noch 'planned' bzw. 'open'), und setzt abgeholt_at. Eine Zeile je Plan und Art (Upsert).
-- Lesen + abgeholt_at setzen nur der Besitzer des Plans (RLS über trade_plans.user_id); schreiben nur die Railway-Route.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

create table if not exists public.puls_ergebnisse (
  plan_id     text not null,
  art         text not null check (art in ('order', 'close')),
  pc_id       text check (pc_id is null or pc_id ~ '^pc-[a-z0-9]{4,12}$'),
  stufe       text not null default 'ende' check (stufe in ('geklickt', 'ende')),
  ergebnis    jsonb not null default '{}'::jsonb,
  at          timestamptz not null default now(),
  abgeholt_at timestamptz,
  primary key (plan_id, art)
);
alter table public.puls_ergebnisse enable row level security;

drop policy if exists puls_ergebnisse_lesen on public.puls_ergebnisse;
create policy puls_ergebnisse_lesen on public.puls_ergebnisse for select to authenticated
  using (exists (select 1 from public.trade_plans p where p.id::text = puls_ergebnisse.plan_id and p.user_id = auth.uid()));

drop policy if exists puls_ergebnisse_abholen on public.puls_ergebnisse;
create policy puls_ergebnisse_abholen on public.puls_ergebnisse for update to authenticated
  using (exists (select 1 from public.trade_plans p where p.id::text = puls_ergebnisse.plan_id and p.user_id = auth.uid()))
  with check (exists (select 1 from public.trade_plans p where p.id::text = puls_ergebnisse.plan_id and p.user_id = auth.uid()));

-- Der Tab darf NUR abgeholt_at setzen — das Ergebnis selbst schreibt allein der Bot über Railway.
revoke insert, update, delete on public.puls_ergebnisse from anon, authenticated;
grant select on public.puls_ergebnisse to authenticated;
grant update (abgeholt_at) on public.puls_ergebnisse to authenticated;

create index if not exists puls_ergebnisse_offen on public.puls_ergebnisse (at) where abgeholt_at is null;

-- Lesen (Admin):
-- select plan_id, art, pc_id, stufe, at, abgeholt_at, ergebnis->>'code' code, ergebnis->>'einstieg' einstieg
--   from public.puls_ergebnisse order by at desc limit 20;

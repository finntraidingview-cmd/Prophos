-- POLAR (13.10.2026, Finn): Funded-Futures (ID A, TradingView, PC A) gegen Funded-CFD (ID B, MT5, PC B) als Airbag statt
-- Fusion-Live. Indirekter Master = Futures, indirekter Slave = CFD. Beide Puls bereiten die Order bis kurz vor den Klick vor,
-- melden „bereit", Railway gibt EINE Feuerzeit, beide klicken gleichzeitig. Master korrigiert TP/SL nach dem Fill, Slave setzt
-- SL/TP per Klick auf ~102,5 % der Master-Abstände und parkt die Maus auf dem ✕. Master zu (Reader) → Railway → Slave-Panel
-- → ein Klick. Nie per EA schließen (FundedNext ≥ 50k = nur manuell, Deal-Grund sichtbar).
-- Rein additiv: neuer Weg 'polar', zwei Spalten, eine Lauf-Tabelle. Bestehende Wege unverändert.

-- 1) Plan-Felder: Slave gehört einer ANDEREN ID (slave_account_id gibt es schon), Prozent der Slave-Level
alter table public.trade_plans add column if not exists polar_slave_user_id uuid;
alter table public.trade_plans add column if not exists polar_pct numeric;
comment on column public.trade_plans.polar_slave_user_id is 'Polar: Supabase-User der Slave-ID (CFD-Konto slave_account_id)';
comment on column public.trade_plans.polar_pct is 'Polar: Slave-SL/TP in % der Master-Abstände vom eigenen Fill (Finn 102,5–103)';

-- 2) Weg 'polar' = mit Hedge (Funded-Regel lässt ihn zu) und Big Trade (ein Big Trade je ID/Fenster gleichzeitig)
create or replace function public.prophos_hedge_weg(p_route text, p_hedge_eur numeric, p_orbit_v3 boolean, p_winning_day boolean)
returns boolean language sql immutable as $$
  select case
    when coalesce(p_route, '') in ('mt5', 'tvplus', 'dup', 'polar') then true
    when coalesce(p_route, '') in ('mt5v2', 'tvv2', 'tsv2')
      then (coalesce(p_hedge_eur, 0) > 0 or coalesce(p_orbit_v3, false) or coalesce(p_winning_day, false))
    else null
  end
$$;

create or replace function public.prophos_big_trade(p_route text, p_hedge_eur numeric, p_orbit_v3 boolean, p_winning_day boolean)
returns boolean language sql immutable as $$
  select coalesce(p_route, '') = 'polar'
      or (coalesce(p_route, '') in ('tvv2', 'tsv2') and coalesce(public.prophos_hedge_weg(p_route, p_hedge_eur, p_orbit_v3, p_winning_day), false))
$$;

-- 3) Lauf-Tabelle: ein Polar-Durchgang je Zeile. Schreiben nur Railway (service role); lesen Master- und Slave-ID.
create table if not exists public.polar_lauf (
  id               uuid primary key default gen_random_uuid(),
  plan_id          uuid not null references public.trade_plans(id) on delete cascade,
  master_user_id   uuid not null,
  slave_user_id    uuid not null,
  status           text not null default 'start'
                   check (status in ('start', 'bereit', 'feuer', 'offen', 'master_zu', 'fertig', 'abbruch', 'fehler')),
  master_bereit_at timestamptz,
  slave_bereit_at  timestamptz,
  feuer_ms         bigint,           -- gemeinsame Feuerzeit (Railway-Uhr, Epoch ms)
  master           jsonb not null default '{}'::jsonb,   -- Fill, Klick-ms, Level, Ende, Balance
  slave            jsonb not null default '{}'::jsonb,   -- Fill, Ticket, Level, ✕-geparkt, Klick-ms, Ende, Balance
  master_zu_ms     bigint,           -- Reader sah Master flach (Railway-Uhr)
  slave_zu_ms      bigint,           -- Slave-✕ geklickt + bewiesen
  grund            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists polar_lauf_plan on public.polar_lauf (plan_id, created_at desc);
create index if not exists polar_lauf_aktiv on public.polar_lauf (status) where status not in ('fertig', 'abbruch', 'fehler');
drop trigger if exists polar_lauf_updated on public.polar_lauf;
create trigger polar_lauf_updated before update on public.polar_lauf for each row execute function set_updated_at();

alter table public.polar_lauf enable row level security;
drop policy if exists polar_lauf_lesen on public.polar_lauf;
create policy polar_lauf_lesen on public.polar_lauf for select to authenticated
  using (auth.uid() = master_user_id or auth.uid() = slave_user_id);

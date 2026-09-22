-- 2026-09-22: Winning-Day-Farmer (Finn: „automatischer Winning Day Farmer — ich will nie wieder
-- Winning Days manuell fahren müssen; ab 02:00, welche ID zuerst kommt ist Zufall, dann Pause
-- 15 min–1 h, dann die nächste ID; das Würfeln will ich um 00:00 schon kennen und bearbeiten").
-- Jede ID = eigener Prophos-Nutzer (RLS trennt accounts/trade_plans strikt). Der Farmer braucht
-- deshalb zwei NUTZERÜBERGREIFENDE Tabellen: eine Regelzeile für alle Tabs und den Tagesplan
-- (eine Zeile je Tag × Nutzer), den jeder PC-Tab für sich einträgt und aus dem er seinen Slot liest.
create table if not exists public.wd_farmer_regeln (
  id          integer primary key default 1 check (id = 1),
  aktiv       boolean not null default false,
  start_hhmm  text    not null default '02:00',
  tz          text    not null default 'Asia/Dubai',
  jitter_min  integer not null default 10,   -- erste ID: 0–jitter_min min nach der Startzeit
  pause_min   integer not null default 15,   -- Pause zwischen zwei IDs (Zufall zwischen min und max)
  pause_max   integer not null default 60,
  abstand_min integer not null default 2,    -- Abstand zwischen zwei Konten derselben ID
  abstand_max integer not null default 4,
  vorplan     jsonb,                          -- {instr, kt, regeln:{ch, fu, staffel}} aus „Futures vorplanen"
  updated_at  timestamptz not null default now(),
  updated_by  uuid
);

create table if not exists public.wd_tagesplan (
  tag            date not null,
  user_id        uuid not null,
  name           text,
  konten         jsonb not null default '[]'::jsonb,   -- [{id,name,firm,aktiv,tpVon,tpBis,slave,waehrung,puffer,fehler}]
  reihenfolge    integer,
  start_um       timestamptz,
  richtung       text check (richtung in ('buy','sell')),
  status         text not null default 'geplant',      -- geplant | leer | laeuft | fertig | verpasst
  ergebnis       jsonb,
  registriert_at timestamptz not null default now(),
  gestartet_at   timestamptz,
  updated_at     timestamptz not null default now(),
  primary key (tag, user_id)
);

alter table public.wd_farmer_regeln enable row level security;
alter table public.wd_tagesplan     enable row level security;

-- Bewusst offen für alle angemeldeten Nutzer: Finn plant den Tag über alle IDs hinweg
-- (Profil-Umschalter am Mac), die PC-Tabs lesen fremde Zeilen für die Reihenfolge.
-- Keine Geheimnisse drin — nur Zeiten, Richtungen, Kontonamen.
drop policy if exists "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln;
create policy "wd_farmer_regeln angemeldet" on public.wd_farmer_regeln
  for all to authenticated using (true) with check (true);
drop policy if exists "wd_tagesplan angemeldet" on public.wd_tagesplan;
create policy "wd_tagesplan angemeldet" on public.wd_tagesplan
  for all to authenticated using (true) with check (true);

insert into public.wd_farmer_regeln (id) values (1) on conflict (id) do nothing;

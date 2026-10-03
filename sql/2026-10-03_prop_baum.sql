-- Prop-Baum (03.10.2026, Auftrag von Pascal, Finn: „bau es mal in Prophos rein … fass nix bestehendes an").
-- Admin-Reiter „Prop-Baum": alle aktiven Prop-Accounts als Baum Firma → Stufe → ID → Account, je Handelstag
-- (Wechsel 17:45 America/New_York) abhaken. Zwei NEUE Tabellen, nichts Bestehendes wird verändert.
--
-- Beide Tabellen schreibt und liest NUR das Backend (/admin/prop-baum, Service-Key, an RLS vorbei) — dort
-- greifen Login-Prüfung und „nur eigene" (admin_zugang) wie bei /admin/overview. RLS an, keine Policy:
-- ein Browser kommt mit dem Anon-/User-Token gar nicht dran (wie die übrigen Admin-Tabellen, die nur
-- über Railway laufen). Die ID-Auswahl je Nutzer liegt in user_settings (key 'prop_baum_ids'), dafür
-- braucht es keine Tabelle.

-- Haken je Account und Handelstag. art 'done' = von Hand abgehakt, 'skip' = ein von Prophos erkannter
-- Trade wurde von Hand wieder entfernt (zählt an diesem Handelstag nicht als erledigt).
create table if not exists public.prop_baum_haken (
  account_id uuid not null references public.accounts(id) on delete cascade,
  handelstag date not null,
  art        text not null check (art in ('done', 'skip')),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (account_id, handelstag)
);

-- Tages-Schnappschuss: der ERSTE gesehene Stand je Account am Handelstag (Rohwerte, die Stufe rechnet das
-- Frontend daraus mit derselben Logik wie für den aktuellen Stand). Daraus entstehen der Pfeil „↑ Neu"
-- (Stufe hat sich heute geändert) und der rote Chip für heute archivierte Accounts — das Archiv selbst
-- trägt keinen Zeitstempel. Eingefügt wird nur, was am Tag noch fehlt (on conflict do nothing).
create table if not exists public.prop_baum_schnappschuss (
  account_id uuid not null references public.accounts(id) on delete cascade,
  handelstag date not null,
  daten      jsonb not null,
  created_at timestamptz not null default now(),
  primary key (account_id, handelstag)
);

alter table public.prop_baum_haken enable row level security;
alter table public.prop_baum_schnappschuss enable row level security;

create index if not exists prop_baum_haken_tag on public.prop_baum_haken (handelstag);
create index if not exists prop_baum_schnappschuss_tag on public.prop_baum_schnappschuss (handelstag);

-- 22.10.2026 (Finn): „Ich will mich auf meinem Handy oder Pascal auf seinem Handy mit der Master-ID, also Finn + Pascal oder Pascal,
-- einloggen. Dann bekommen wir alle Notifications von Prophos … mit den Prioritäten, wenn irgendwas schiefgeht" — z. B. Puls kehrt nach
-- einer Order nicht ins Orbit-Konto zurück, Radar musste schließen, ein Hedge bleibt offen.
-- alarm_empfaenger  wer alles bekommt (Master-IDs) und ab welcher Stufe gepusht wird:
--                   1 = nur sofort (Geld in Gefahr), 2 = sofort + wichtig (Standard), 3 = alles inkl. Info (Trade läuft/beendet …)
-- alarm_log         jede Meldung einmal (auch die nicht gepushten), Grundlage für die Liste in den Einstellungen und für Auswertungen
--                   wie „wie lange hat der Heimweg gedauert" (art heimweg_ok/heimweg_fehl, daten.dauer_ms). Railway räumt nach 30 Tagen.
-- Beide Tabellen nur über Railway (service_role) — RLS an, keine Policy. Wiederholbar.
create table if not exists public.alarm_empfaenger (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  min_prio   smallint not null default 2 check (min_prio between 1 and 3),
  aktiv      boolean not null default true,
  notiz      text,
  erstellt_at timestamptz not null default now()
);
alter table public.alarm_empfaenger enable row level security;

create table if not exists public.alarm_log (
  id         bigserial primary key,
  at         timestamptz not null default now(),
  prio       smallint not null check (prio between 1 and 3),
  art        text not null,
  titel      text not null,
  text       text not null default '',
  uid        uuid,                 -- betroffene ID (nicht der Empfänger)
  plan_id    text,
  schluessel text,
  daten      jsonb not null default '{}'::jsonb,
  zugestellt int not null default 0,
  geraete    int not null default 0
);
create index if not exists alarm_log_at on public.alarm_log (at desc);
create index if not exists alarm_log_art_at on public.alarm_log (art, at desc);
alter table public.alarm_log enable row level security;

insert into public.alarm_empfaenger (user_id, min_prio, notiz) values
  ('48f272b4-913e-4598-a06a-1dcc3d5679fb', 2, 'Finn + Pascal — Master-ID (Finn 22.10.2026)'),
  ('728b4d23-ff5c-45f9-b6de-9b75c1f9a78a', 2, 'Pascal — Master-ID (Finn 22.10.2026)')
on conflict (user_id) do nothing;

select e.user_id, u.raw_user_meta_data->>'name' as name, e.min_prio, e.aktiv from public.alarm_empfaenger e join auth.users u on u.id = e.user_id;

-- Rückbau:
-- drop table if exists public.alarm_log; drop table if exists public.alarm_empfaenger;

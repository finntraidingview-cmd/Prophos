-- 2026-09-23: Kompass-Regeln für die Richtungs-Vorwahl im V2-Popup (Finn: „wenn die Konfidenz 5/5 ist,
-- 90 %; 4/5 → 80 %; 3/5 → 75 %; sonst 70 — und im Admin änderbar"). EINE Zeile für alle IDs (Muster
-- wd_farmer_regeln): das Plan-Popup läuft in jedem Profil, die Quote soll überall dieselbe sein.
-- Keine Geheimnisse drin — vier Prozentzahlen.
create table if not exists public.kompass_regeln (
  id              integer primary key default 1 check (id = 1),
  quoten          jsonb not null default '{"5":90,"4":80,"3":75,"sonst":70}'::jsonb,
  aktualisiert_at timestamptz not null default now()
);
alter table public.kompass_regeln enable row level security;
drop policy if exists "kompass_regeln angemeldet" on public.kompass_regeln;
create policy "kompass_regeln angemeldet" on public.kompass_regeln
  for all to authenticated using (true) with check (true);
insert into public.kompass_regeln (id) values (1) on conflict (id) do nothing;

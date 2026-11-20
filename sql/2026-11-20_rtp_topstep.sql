-- TS1 — Add-on „Responsible Trader Programm“ (RTP) für Topstep (Finn 20.11.2026 ~05:15 Dubai: „einfach mal bauen“).
-- Spezifikation: .claude/master/berichte/2026-11-20_TS1_topstep_rtp_konstrukt.md; Regelbasis TS0 (help.topstep.com, 20.11.2026).
-- Planer: app.py fdp_planen (RTP-Weg, Rechnung in rtp_topstep.py). Idempotent. Nutzt addon_firma aus sql/2026-11-20_striking_apex.sql
-- (Zeile (user_id, 'topstep', 'rtp', true), Schreiben nur wd_admin) — diese Datei also DANACH einspielen.
-- Eigenes Gate wie Striking: rtp_regeln.aktiv (globaler Not-Aus, Standard AUS) + addon_firma-Zeile je ID + Topstep Funded Futures mit Balance.
-- Topstep bleibt im Funded-Planer an=false — RTP läuft daran vorbei, nur für freigeschaltete IDs.

create table if not exists public.rtp_regeln (
  id         int primary key default 1 check (id = 1),
  topstep    jsonb not null default '{}'::jsonb,
  aktiv      boolean not null default false,
  updated_at timestamptz not null default now()
);

-- dll/mll/Puffer/Toleranzen hat der Planer als Standard (rtp_topstep.py RTP_STANDARD); hier nur die Werte aus der Spezifikation,
-- jeder weitere Schlüssel überschreibt den Standard
insert into public.rtp_regeln (id, topstep) values (1, '{
  "ziel":       [28000, 30000],
  "deckel_pct": 40,
  "tag1_pct":   40,
  "sl":         [2500, 3000],
  "kontrakte":  [2, 3],
  "symbol":     "NQ"
}'::jsonb)
on conflict (id) do nothing;

alter table public.rtp_regeln enable row level security;
drop policy if exists rtp_regeln_lesen on public.rtp_regeln;
create policy rtp_regeln_lesen on public.rtp_regeln for select to authenticated using (true);
drop policy if exists rtp_regeln_admin on public.rtp_regeln;
create policy rtp_regeln_admin on public.rtp_regeln for all to authenticated using (public.wd_admin()) with check (public.wd_admin());

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.rtp_regeln to backup_reader';
    execute 'drop policy if exists backup_reader_select on public.rtp_regeln';
    execute 'create policy backup_reader_select on public.rtp_regeln for select to backup_reader using (true)';
  end if;
end $$;

-- Freischalten (nur auf Finns Wort, je ID einzeln):
-- insert into public.addon_firma (user_id, firma, addon, an) values ('<user_id>', 'topstep', 'rtp', true)
--   on conflict (user_id, firma, addon) do update set an = excluded.an, updated_at = now();
-- update public.rtp_regeln set aktiv = true, updated_at = now() where id = 1;

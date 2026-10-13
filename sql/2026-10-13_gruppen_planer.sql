-- GRUPPEN-PLANER (13.10.2026, Finn: „für Emin so eine kleinere Variante … alle Echo-Trades mit Gegenhedge bei allen seinen CFD-Dingern,
-- bei allen seinen drei IDs … von 7:00 bis 17:20 deutscher Zeit … das System komplett separat betrachten").
-- 1) auto_plan_gruppe: eine Zeile je Verwalter-Gruppe mit eigenem Planer (app.py gp_planen / gp_tick, Route /admin/gruppen-plan).
--    Finns auto_plan_regeln bleibt unberührt — die Firmen-Regeln (TP/SL/Lots) liest der Gruppen-Planer nur mit.
-- 2) Firmen-Abstand (1 min je Firma über IDs) nur noch innerhalb derselben Gruppe: Emins IDs schieben HT-Starts nicht mehr und umgekehrt.

create table if not exists public.auto_plan_gruppe (
  gruppe_id   uuid primary key references public.id_gruppen(id) on delete cascade,
  aktiv       boolean not null default false,
  zeiten      jsonb not null default '{}'::jsonb,   -- {tz, von, bis, lauf, abstand_id_min}; fehlende Felder = GP_ZEITEN_STANDARD
  letzter_lauf jsonb,
  updated_at  timestamptz not null default now()
);
alter table public.auto_plan_gruppe enable row level security;   -- nur Railway (service role) liest/schreibt

insert into public.auto_plan_gruppe (gruppe_id, aktiv, zeiten)
select g.id, true, '{"tz": "Europe/Berlin", "von": "07:00", "bis": "17:20", "lauf": "06:00", "abstand_id_min": 3}'::jsonb
  from public.id_gruppen g
 where g.name = 'Emin' and g.verwalter_user_id is not null
on conflict (gruppe_id) do nothing;

-- Gruppe einer ID (null = in keiner Gruppe, zählt wie HT ohne Eintrag)
create or replace function public.prophos_gruppe_von(uid uuid)
returns uuid language sql stable security definer set search_path to 'public' as $$
  select m.gruppe_id from public.id_gruppe_mitglied m where m.user_id = uid order by m.gruppe_id limit 1
$$;

CREATE OR REPLACE FUNCTION public.trade_plans_firmen_abstand()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  letzter timestamptz;
  ziel timestamptz;
  grp uuid;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  grp := public.prophos_gruppe_von(new.user_id);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- 13.10.2026 (Gruppen-Planer Emin): nur IDs derselben Gruppe zählen — Emin-Gruppe und HT sind getrennte Systeme
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at)
    into letzter
    from public.trade_plans p
   where p.id <> new.id
     and p.user_id is distinct from new.user_id
     and public.prophos_gruppe_von(p.user_id) is not distinct from grp
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return new;
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': eine andere ID hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 1 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai)',
            'start');
  end if;
  return null;
end $function$;

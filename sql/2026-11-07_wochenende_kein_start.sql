-- WE1 · AM MARKT-WOCHENENDE NIE EINE ORDER (07.11.2026, Slave 4 — Vorfall Sa 07.11. 07:18 Dubai: Moritz Tradeify 150k …9823, Plan 63d32af5,
-- finaler Tradeify mit Orbit-Hedge. trade_plans_a_final_halten hatte den Start Fr 06.11. 06:38 wegen „Fusion-Marge knapp" um +1 Tag geschoben, auf
-- Sa 06:52 Dubai; tfh_tick stellte Sa 06:33 auf Hedge „mit", Puls klickte 07:17 bei geschlossenem Markt, kein Fill, Plan review mit P&L 0).
-- Markt-Wochenende = CME/Globex Fr 16:00 CT bis So 17:00 CT, für Starts mit 5 min Puffer ab Fr 15:55 CT (Puls braucht bis zur Order Sekunden–Minuten;
-- Sommer/Winter über America/Chicago; Winter: Sa 01:55 – Mo 03:00 Dubai) — dieselbe Regel
-- wie app.py cme_wochenende / _cme_offen_seit_s und cmeWochenende im Tab. NAS100-CFD ist in derselben Zeit zu.
--   1) prophos_markt_wochenende(t) und prophos_naechster_handelstag(t): Wochenende → gleiche Uhrzeit (gleicher Jitter) am nächsten Handelstag;
--      fällt das Ergebnis in die tägliche CME-Pause 16:00–17:00 CT, eine Stunde später.
--   2) trade_plans_a_final_halten: das Ziel „+1 Tag" landet nie mehr im Wochenende (Patch per Textersatz am Live-Text wie LF1, sonst zeichengleich).
--   3) Claim-Riegel trade_plans_a00_wochenende (Postgres feuert gleichartige Trigger alphabetisch: nach a00_konto_deaktiviert, vor a0_*, a1_*,
--      a_final_halten, big_trade …): am Wochenende wird kein Start-Claim geschrieben; der Plan bleibt
--      planned, start_um unverändert, Marke start_sperre art 'wochenende' (nur beim ersten Mal). Verbrauch-Claims (start_claim_art 'verbrauch') laufen
--      durch — sie schließen einen Plan nur ab, senden nichts.
-- Wiederholbar. Rückbau: sql/2026-11-07_wochenende_kein_start_rueckbau.sql.

create or replace function public.prophos_markt_wochenende(p_t timestamptz)
returns boolean
language sql
stable
as $$
  select case extract(isodow from (p_t at time zone 'America/Chicago'))::int
           when 6 then true                                                            -- Samstag
           when 5 then (p_t at time zone 'America/Chicago')::time >= time '15:55'      -- Freitag ab 15:55 CT (5 min Puffer vor dem Schluss 16:00)
           when 7 then (p_t at time zone 'America/Chicago')::time <  time '17:00'      -- Sonntag vor 17:00 CT
           else false
         end
$$;

create or replace function public.prophos_naechster_handelstag(p_t timestamptz)
returns timestamptz
language plpgsql
stable
as $$
declare
  t timestamptz := p_t;
  i int := 0;
begin
  if t is null then
    return null;
  end if;
  while public.prophos_markt_wochenende(t) and i < 4 loop      -- Sa → So → Mo (gleiche Uhrzeit, gleicher Jitter)
    t := t + interval '1 day';
    i := i + 1;
  end loop;
  if i > 0 and (t at time zone 'America/Chicago')::time >= time '16:00' and (t at time zone 'America/Chicago')::time < time '17:00' then
    t := t + interval '1 hour';                                -- nicht in die tägliche CME-Pause
  end if;
  return t;
end $$;

-- 2) final_halten: Ziel nie im Wochenende
do $patch$
declare
  def text;
  alt text := $a$  if ziel < now() + interval '12 hours' then
    ziel := now() + interval '1 day' + make_interval(secs => floor(random() * 1200));
  end if;
$a$;
  neu text := $b$  if ziel < now() + interval '12 hours' then
    ziel := now() + interval '1 day' + make_interval(secs => floor(random() * 1200));
  end if;
  ziel := public.prophos_naechster_handelstag(ziel);   -- WE1 (07.11.2026): nie aufs Markt-Wochenende
$b$;
begin
  def := pg_get_functiondef('public.trade_plans_a_final_halten()'::regprocedure);
  if position('prophos_naechster_handelstag' in def) > 0 then
    raise notice 'final_halten: schon gepatcht';
  elsif position(alt in def) = 0 then
    raise exception 'final_halten: Stelle „+1 Tag" nicht gefunden — Live-Text geändert, Patch nicht angewendet';
  else
    execute replace(def, alt, neu);
  end if;
end $patch$;

-- 3) Claim-Riegel am Wochenende
create or replace function public.trade_plans_a00_wochenende()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
begin
  if new.status is distinct from 'planned' or coalesce(new.start_claim_art, '') = 'verbrauch' then
    return new;
  end if;
  if not public.prophos_markt_wochenende(now()) then
    return new;
  end if;
  if coalesce(new.mt5_baseline->'start_sperre'->>'art', '') <> 'wochenende' then
    update public.trade_plans
       set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'wochenende', 'text', 'Markt-Wochenende (CME zu bis So 17:00 Chicago) — kein Start, der Plan bleibt geplant',
             'at', now(), 'naechster', public.prophos_naechster_handelstag(now()), 'versuche', 1))
     where id = new.id;
  end if;
  return null;                                                  -- Claim nicht schreiben: Plan bleibt planned, start_um unverändert
end $$;

drop trigger if exists trade_plans_a00_wochenende on public.trade_plans;
create trigger trade_plans_a00_wochenende
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a00_wochenende();

-- Prüfen (nur lesen):
--   select prophos_markt_wochenende('2026-11-07 03:18Z'), prophos_markt_wochenende('2026-11-09 03:18Z');            -- Sa 07:18 Dubai → t · Mo → f
--   select prophos_naechster_handelstag('2026-11-07 02:52Z') at time zone 'Asia/Dubai';                               -- Sa 06:52 → Mo 06:52 Dubai

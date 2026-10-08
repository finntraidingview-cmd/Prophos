-- GEGENHEDGE ÜBER IDs AM START (08.10.2026, Slave-Terminal 4 — Master/Finn: „eigene Lücken finden und schließen"; der Ausgleichs-Bot
-- sperrt seit 3d43e4e Gegenhedges über IDs je Firma beim PLANEN, am START prüft aber nichts: rkVorStart, v2RichtungKonflikt und
-- firmGeplanteRichtungen sehen per RLS nur die eigene ID („users can view own trade_plans"), firmLiveRichtungen verwirft fremde IDs
-- absichtlich („Fremde ID → geht uns nichts an", 26.08.2026). Hand-Start, „Jetzt starten", Neu einplanen, verpasste Starts und alte
-- Tab-Stände konnten so eine ID gegen eine andere ID derselben Firma öffnen — für die Firma ein Gegenhedge zwischen zwei Personen.)
--
-- Sitzt wie der Firmen-Abstand am Claim (trade_plans.start_um_gestartet_at NULL → gesetzt, jeder Startweg des PC-Tabs). Trigger feuern
-- alphabetisch: trade_plans_firmen_abstand zuerst; gibt der NULL zurück, kommt dieser gar nicht mehr dran.
-- Gesperrt (Claim nicht geschrieben → Update trifft keine Zeile → der Tab startet nicht, suClaimFehlgriff liest den Plan neu):
--   (a) eine ANDERE ID läuft bei derselben Firma (prophos_firma_key) in GEGENRICHTUNG: status open, Orbit gesendet (≤ 10 min) oder
--       Claim ohne Start (≤ 2 min, Start unterwegs) → start_um = jetzt + 30 min (+ 20–90 s Streuung). Läuft die Gegenseite weiter,
--       schiebt jeder neue Claim wieder um 30 min — höchstens eine Protokollzeile je Schub.
--   (b) eine ANDERE ID hat einen gegenläufigen Start (bestätigt oder Hand, noch nicht geclaimt), der FRÜHER liegt als unserer
--       (gleich: kleinere id zuerst) und höchstens 30 min alt ist → start_um = deren Start + 30 min. „Der Spätere weicht" wie
--       app.py _ap_firma_konflikt — sonst schöben sich zwei gegenläufige Pläne gegenseitig immer weiter (± 30 min auf beiden Seiten).
-- Fenster 30 min = AP_GEGEN_FIRMA_MIN (app.py _ap_gegen_firma). Protokoll in auto_plan_umplanung (quelle 'start', „[Gegenhedge] …").
-- Nicht gesperrt: gleiche ID (dort gelten Richtungsschutz/rkVorStart), gleiche Richtung, andere Firma, unbestätigte Vorschläge der
-- Gegenseite, beendete Pläne, „verpasst"-Claims (Startzeit über 60 min her: der Tab startet dann nichts).
--
-- VORAUSSETZUNG: sql/2026-10-08_firmen_abstand_riegel.sql (prophos_firma_key + derselbe Advisory-Lock je Firma). Diese Datei bricht
-- ab, wenn prophos_firma_key fehlt. Wiederholbar. Rückbau:  drop trigger if exists trade_plans_gegenhedge on public.trade_plans;
-- drop function if exists public.prophos_gegenhedge_halten(uuid); drop function if exists public.trade_plans_gegenhedge();
-- drop function if exists public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz);
-- Dazu die RPC prophos_gegenhedge_halten (unten) für Hand-Starts/„Neu starten“ — der PC-Tab fragt sie in faVorStart.

do $pruef$
begin
  perform 'public.prophos_firma_key(text)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-08_firmen_abstand_riegel.sql einspielen (prophos_firma_key fehlt)';
end $pruef$;

-- Gemeinsame Rechnung für Trigger und RPC: Konflikt eines Plans (id, ID, Firma, Richtung, eigene Startzeit) → (ziel, wer, grund)
-- oder keine Zeile. Liest fremde Pläne (security definer), gibt nur Zeitpunkt, ID und Grund heraus.
create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)
returns table(ziel timestamptz, wer uuid, grund text)
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firma);
  gegen text := case p_richtung when 'buy' then 'sell' when 'sell' then 'buy' else null end;
  t timestamptz;
  u uuid;
begin
  if gegen is null or coalesce(btrim(p_firma), '') = '' then
    return;
  end if;
  -- (a) eine andere ID läuft gegenläufig (oder ihr Start ist gerade unterwegs)
  select coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, now()), p.user_id
    into t, u
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id is distinct from p_user
     and p.richtung = gegen
     and (p.status = 'open'
          or (p.status = 'planned' and (p.orbit_gesendet_at > now() - interval '10 minutes'
                                        or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null))))
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if t is not null then
    return query select now() + interval '30 minutes', u,
      'läuft dort in Gegenrichtung (seit ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)';
    return;
  end if;
  -- (b) eine andere ID startet gegenläufig früher (bestätigt/Hand, noch nicht geclaimt, höchstens 30 min alt) — der Spätere weicht
  select p.start_um, p.user_id
    into t, u
    from public.trade_plans p
   where p.id <> p_id
     and p.user_id is distinct from p_user
     and p.richtung = gegen
     and p.status = 'planned'
     and p.start_um_gestartet_at is null
     and (not coalesce(p.auto_plan, false) or p.auto_bestaetigt_at is not null)
     and p.start_um >= now() - interval '30 minutes'
     and (p.start_um < p_ref or (p.start_um = p_ref and p.id < p_id))
     and public.prophos_firma_key(p.master_firm) = k
   order by p.start_um desc
   limit 1;
  if t is not null then
    return query select greatest(t + interval '30 minutes', now() + interval '5 minutes'), u,
      'startet dort um ' || to_char(t at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai in Gegenrichtung';
  end if;
end $$;
revoke all on function public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamptz) from public;

create or replace function public.trade_plans_gegenhedge() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  c record;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));   -- derselbe Lock wie der Firmen-Abstand
  select * into c from public.prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()));
  if c.ziel is null then
    return new;                                   -- frei: Claim normal schreiben
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: kein Claim-Trigger feuert dafür
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Gegenhedge] ' || k || ': eine andere ID ' || c.grund || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$;

drop trigger if exists trade_plans_gegenhedge on public.trade_plans;
create trigger trade_plans_gegenhedge
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_gegenhedge();

-- RPC VOR JEDEM START (faVorStart im PC-Tab, wie prophos_firmen_abstand_halten): Hand-Starts ohne Claim und „Neu starten" (Claim bleibt
-- gesetzt) laufen am Trigger vorbei. Nur der eigene Plan (auth.uid() = user_id); Order schon draußen (started_at/orbit_gesendet_at) →
-- frei, kein Eingriff. Konflikt → start_um = Ziel + 20–90 s, Claim gelöst (der Tick startet zur neuen Zeit, der Trigger prüft erneut),
-- Protokoll. Name der anderen ID nur als Vorname aus user_metadata.name, sonst die ersten 8 Zeichen — nie die E-Mail.
create or replace function public.prophos_gegenhedge_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
  c record;
  ziel timestamptz;
  name text;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or coalesce(btrim(pl.master_firm), '') = '' or pl.richtung not in ('buy', 'sell') then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  select * into c from public.prophos_gegenhedge_konflikt(pl.id, pl.user_id, pl.master_firm, pl.richtung, coalesce(pl.start_um, now()));
  if c.ziel is null then
    return jsonb_build_object('frei', true);
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 70));
  select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(c.wer::text, 8))
    into name from auth.users u where u.id = c.wer;                                -- nur Vorname, nie E-Mail
  if pl.start_um is null or pl.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Gegenhedge] ' || k || ': ' || coalesce(name, 'andere ID') || ' ' || c.grund || ' — Start (Neu starten/von Hand) wartet bis '
            || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'grund', c.grund);
end $$;

revoke all on function public.prophos_gegenhedge_halten(uuid) from public;
grant execute on function public.prophos_gegenhedge_halten(uuid) to authenticated;

-- FIRMEN-ABSTAND VOR JEDEM START (08.10.2026, Slave-Terminal 3 — Finn 05:00 Dubai: „5-Minuten-Regel gleiche Prop-Firm — gefixt? Falls
-- nicht, kümmer dich um alles!"). Der Claim-Riegel (sql/2026-10-08_firmen_abstand_riegel.sql) greift nur, wenn start_um_gestartet_at
-- von NULL auf gesetzt geht. „Neu starten" (Claim bleibt gesetzt) und Hand-Starts ohne Claim liefen daran vorbei. Darum fragt der
-- PC-Tab vor JEDEM Start (tpOrbitStartenKern, tpJetztStarten) diese Funktion. Sie braucht security definer, weil RLS einem Login nur
-- die eigenen Pläne zeigt — sie gibt nichts über fremde Pläne heraus außer „frei / ab wann / welche ID".
-- Regel = Trigger: eine ANDERE ID hat bei derselben Firma (prophos_firma_key) in den letzten 5 min WIRKLICH gestartet (started_at /
-- orbit_gesendet_at) oder vor ≤ 2 min geclaimt ohne Start. Dann: start_um → deren Start + 5 min + 20–90 s, Claim gelöst (der Tick
-- startet ihn zur neuen Zeit, der Claim-Riegel prüft dann erneut), Protokoll in auto_plan_umplanung (quelle 'start'). Nur der eigene
-- Plan (auth.uid() = user_id); sonst/ohne Firma: frei.
-- Prüfer 08.10.2026: orbit_gesendet_at („Order an TV gesendet") wird NIE angefasst — hat der eigene Plan schon started_at oder
-- orbit_gesendet_at, ist die Order draußen: „frei", kein Eingriff (sonst wäre bei einem Neustart ein Doppel-Kauf denkbar).
-- Name der anderen ID nur als Vorname aus user_metadata.name, sonst die ersten 8 Zeichen der ID — nie die E-Mail.
-- Setzt prophos_firma_key aus sql/2026-10-08_firmen_abstand_riegel.sql voraus (vorher einspielen). Wiederholbar.
-- Rückbau: drop function if exists public.prophos_firmen_abstand_halten(uuid);

create or replace function public.prophos_firmen_abstand_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
  letzter timestamptz;
  wer uuid;
  ziel timestamptz;
  name text;
begin
  select * into pl from public.trade_plans where id = p_plan;
  if not found or pl.user_id is distinct from auth.uid() then
    return jsonb_build_object('frei', true, 'grund', 'kein eigener Plan');
  end if;
  if pl.status is distinct from 'planned' or coalesce(btrim(pl.master_firm), '') = '' then
    return jsonb_build_object('frei', true);
  end if;
  if pl.started_at is not null or pl.orbit_gesendet_at is not null then
    return jsonb_build_object('frei', true, 'grund', 'Order schon gesendet — kein Eingriff');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  select p.user_id,
         case when p.started_at is not null or p.orbit_gesendet_at is not null
              then greatest(coalesce(p.started_at, '-infinity'::timestamptz), coalesce(p.orbit_gesendet_at, '-infinity'::timestamptz))
              else p.start_um_gestartet_at end as t
    into wer, letzter
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id is distinct from pl.user_id
     and (p.started_at > now() - interval '5 minutes'
          or p.orbit_gesendet_at > now() - interval '5 minutes'
          or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null and p.orbit_gesendet_at is null))
     and public.prophos_firma_key(p.master_firm) = k
   order by t desc
   limit 1;
  if letzter is null or letzter <= now() - interval '5 minutes' then
    return jsonb_build_object('frei', true);
  end if;
  ziel := letzter + interval '5 minutes' + make_interval(secs => 20 + floor(random() * 70));
  select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(wer::text, 8))
    into name from auth.users u where u.id = wer;                                   -- nur Vorname, nie E-Mail
  if pl.start_um is null or abs(extract(epoch from pl.start_um - ziel)) > 120 then   -- schon dort (± 2 min): kein zweites Protokoll
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Firmen-Abstand] ' || k || ': ' || coalesce(name, 'andere ID') || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'letzter', letzter);
end $$;

revoke all on function public.prophos_firmen_abstand_halten(uuid) from public;
grant execute on function public.prophos_firmen_abstand_halten(uuid) to authenticated;

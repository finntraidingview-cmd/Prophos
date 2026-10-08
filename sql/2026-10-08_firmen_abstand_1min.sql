-- FIRMEN-ABSTAND 1 MINUTE, JEDE ID (08.10.2026, Slave-Terminal 4 — Finn ~11:50 Dubai: „Wenn es eine andere ID ist, würde ich einfach
-- eine Minute machen, aus Sicherheit … einfach gucken, dass die beiden Orders nicht gleichzeitig starten … nicht in der gleichen
-- Sekunde, dass sich daraus kein Muster entwickelt. Durch den Zufall passiert es eh fast nie." Kurz danach: „wenn Jacob Tradeify long
-- geht, kann er auch 5 min später wieder Tradeify long gehen … Die zwei Regeln mit 60/20 min sind komplett dumm … Nur eben nicht
-- gleichzeitig.")
--
-- Ersetzt trade_plans_firmen_abstand (sql/2026-10-08_firmen_abstand_riegel.sql) und prophos_firmen_abstand_halten
-- (sql/2026-10-08_firmen_abstand_pruefen_rpc.sql) mit gleichen Signaturen; Trigger und prophos_firma_key bleiben, wie sie sind.
-- Neu:
--   * Fenster zentral: prophos_firmen_abstand_fenster() = 60 s (wie app.py AP_FIRMA_ABSTAND_MIN = 1);
--   * zählt JEDER andere Plan derselben Firma (prophos_firma_key) — andere ID wie eigene ID, jede Richtung (vorher nur andere IDs, 5 min);
--   * „deren Start" = der Claim (start_um_gestartet_at), ohne Claim orbit_gesendet_at bzw. started_at — nur in den letzten 60 s
--     (Prüfer Slave 2: started_at liegt 15–40 s nach dem Claim und hätte die Konten-Staffel einer Tranche, 60–120 s, ständig verschoben);
--   * Ziel = deren Start + 60 s + 10–30 s Jitter (vorher + 5 min + 20–90 s); neues start_um nur, wenn es > 30 s abweicht (kein
--     Protokoll-Spam), Texte „[Firmen-Abstand 1 min] …".
-- Unverändert: Riegel am Claim gibt NULL zurück (Tab startet nicht, Tick startet zur neuen Zeit), Lock je Firma, Pläne > 60 min
-- überfällig unberührt, RPC nur für den eigenen Plan, orbit_gesendet_at nie angefasst, Name nur als Vorname. Gegenhedge 90 s
-- (sql/2026-10-08_gegenhedge_90s.sql) ist eine eigene Regel und bleibt.
--
-- Wiederholbar. Rückbau: sql/2026-10-08_firmen_abstand_riegel.sql + sql/2026-10-08_firmen_abstand_pruefen_rpc.sql erneut einspielen.

create or replace function public.prophos_firmen_abstand_fenster() returns interval
language sql immutable as $$ select interval '60 seconds' $$;

create or replace function public.trade_plans_firmen_abstand() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  letzter timestamptz;
  ziel timestamptz;
  eigen boolean;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- jeder andere Plan derselben Firma (auch derselben ID), dessen Start in den letzten 60 s lag — Start = der CLAIM (gewollte Startzeit;
  -- alle Wege haben danach dieselbe Puls-/Echo-Dauer), ohne Claim Order bzw. started_at (Hand: „Läuft"). Prüfer Slave 2: mit started_at
  -- (15–40 s nach dem Claim) hätte der Riegel die eigene Staffel einer Tranche (abstand_konto_s 60–120 s, WD 80 s) ständig verschoben
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at), p.user_id = new.user_id
    into letzter, eigen
    from public.trade_plans p
   where p.id <> new.id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return new;
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));   -- Jitter 10–30 s
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': ' || case when eigen then 'ein anderes Konto dieser ID' else 'eine andere ID' end
            || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 1 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai)',
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$;

create or replace function public.prophos_firmen_abstand_halten(p_plan uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pl public.trade_plans%rowtype;
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
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
  select p.user_id, coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) as t
    into wer, letzter
    from public.trade_plans p
   where p.id <> pl.id
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by t desc
   limit 1;
  if letzter is null or letzter <= now() - f then
    return jsonb_build_object('frei', true);
  end if;
  ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));   -- Jitter 10–30 s
  if wer = pl.user_id then
    name := 'deinem anderen Konto';                                         -- eigene ID (seit 1-min-Regel auch gezählt)
  else
    select coalesce(nullif(split_part(btrim(coalesce(u.raw_user_meta_data->>'name', '')), ' ', 1), ''), left(wer::text, 8))
      into name from auth.users u where u.id = wer;                         -- nur Vorname, nie E-Mail
  end if;
  if pl.start_um is null or abs(extract(epoch from pl.start_um - ziel)) > 30 then
    update public.trade_plans set start_um = ziel, start_um_gestartet_at = null where id = pl.id;   -- orbit_gesendet_at nie
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (pl.id, pl.user_id, pl.master_firm, pl.richtung, pl.richtung, pl.start_um, ziel,
            '[Firmen-Abstand 1 min] ' || k || ': ' || coalesce(name, 'andere ID') || ' hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start (Neu starten/von Hand) wartet bis ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai', 'start');
  else
    ziel := pl.start_um;
    update public.trade_plans set start_um_gestartet_at = null where id = pl.id;
  end if;
  return jsonb_build_object('frei', false, 'ziel', ziel, 'wer', coalesce(name, 'andere ID'), 'firma', k, 'letzter', letzter);
end $$;

revoke all on function public.prophos_firmen_abstand_halten(uuid) from public;
grant execute on function public.prophos_firmen_abstand_halten(uuid) to authenticated;

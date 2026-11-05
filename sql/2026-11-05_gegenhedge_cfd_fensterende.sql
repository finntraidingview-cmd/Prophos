-- R4b (2) GEGENRICHTUNGS-RIEGEL SCHIEBT CFD NIE ÜBER DAS STARTFENSTER (Master 05.11.2026, Befund S7 R4: drei Tradeify-CFD-Challenges — Chris …117785/…117783,
-- Marco …116895 — wurden am 04.11. vom Riegel 34 / 30 / 16 × um je 5–60 min geschoben, weil das Schwesterkonto derselben ID × Firma „Ende nicht gelesen /
-- UNKLAR" hing, und kamen erst 02:00–02:32 Dubai frei = NAS100-/CME-Pause → „Market closed", im Review „nicht gelaufen 0,00" ohne Grund).
-- Nur Challenge-Planer-CFD (auto_plan, route mt5 / mt5v2). Futures, Orbit, Topstep, Polar, Funded und Hand-Pläne: Verhalten unverändert.
-- Neu für diese Pläne im harten Zweig (prophos_gegenrichtung_frei sagt „nicht frei"):
--   • start_sperre trägt erst (erster gesperrter Start); das Fensterende rechnet prophos_cfd_fenster_ende(erst) =
--     least(prophos_waage_fenster_ende(erst) [Planer-Fenster + deutsche Tagesgrenze, wie der Waage-Deckel], zeiten.cfd_bis am Tag von erst).
--   • Läge der nächste Versuch hinter dem Fensterende → nicht weiterschieben, sondern aufgeben: start_sperre {art richtung, status aufgegeben, text
--     „Riegel: Gegenrichtung Schwesterkonto … — nicht gestartet …"}, Protokoll in auto_plan_umplanung, kein Claim.
--   • Einmal aufgegeben (nur für DIESE Startzeit, start_sperre.start): jeder echte Start-Claim wird abgewiesen (kein Order), nur der Verbrauchs-Claim des PC-Tabs (start_claim_art 'verbrauch', „verpasst")
--     geht durch — so endet der Plan wie ein verpasster, und die Endlesung (N2) schreibt den Grund aus start_sperre ins Review.
-- Der 90-s-Zweig (prophos_gegenhedge_konflikt, schiebt 20–40 s) bleibt unverändert.
-- Idempotent (create or replace), nur Funktionen. Rückbau: die Fassung aus sql/2026-10-13_gegenrichtung_hart.sql bzw. pg_get_functiondef vor dem Einspielen
-- (md5 der Live-Fassung 05.11.2026: d618cff8c30ed132730c6b28a630985d). NICHT vom Slave eingespielt.

create or replace function public.prophos_cfd_fenster_ende(p_erst timestamptz)
returns timestamptz
language plpgsql stable security definer set search_path = public as $$
declare
  z jsonb;
  cb jsonb;
  tz text;
  uhr text;
  ende timestamptz := public.prophos_waage_fenster_ende(p_erst);
  bis timestamptz;
begin
  select zeiten into z from public.auto_plan_regeln where id = 1;
  cb := z->'cfd_bis';
  if jsonb_typeof(cb) = 'object' then
    tz := coalesce(nullif(cb->>'tz', ''), 'Europe/Berlin');
    uhr := cb->>'uhr';
  elsif jsonb_typeof(cb) = 'string' then
    tz := 'Europe/Berlin';                 -- "HH:MM" deutscher Zeit (ap_cfd_bis)
    uhr := cb #>> '{}';
  end if;
  if uhr ~ '^\d{1,2}:\d{2}$' then
    bis := (date_trunc('day', p_erst at time zone tz) + uhr::interval) at time zone tz;
    ende := least(ende, greatest(bis, p_erst));   -- erst schon nach cfd_bis → Fenster vorbei (beim ersten Versuch aufgeben)
  end if;
  return ende;
end $$;

create or replace function public.trade_plans_gegenhedge()
returns trigger
language plpgsql security definer set search_path to 'public' as $function$
declare
  k text;
  c record;
  ziel timestamptz;
  hart jsonb;
  txt text;
  cfd boolean;
  ss jsonb;
  erst timestamptz;
  ende timestamptz;
  n int;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  -- R4b: nur Challenge-Planer-CFD bekommt Fensterende und Aufgeben
  cfd := coalesce(new.auto_plan, false) and new.route in ('mt5', 'mt5v2');
  ss := coalesce(old.mt5_baseline->'start_sperre', '{}'::jsonb);
  -- Prüfer-Stopp R4b: aufgegeben gilt nur für genau die Startzeit, bei der aufgegeben wurde — eine neue Uhrzeit (von Hand, Nachholen) startet wieder normal
  if cfd and ss->>'art' = 'richtung' and ss->>'status' = 'aufgegeben' and old.start_um is not null and (ss->>'start') is not null
     and (ss->>'start')::timestamptz = old.start_um then
    if coalesce(new.start_claim_art, '') = 'verbrauch' then
      return new;                          -- Verbrauch sendet nichts — der Plan endet wie ein verpasster
    end if;
    return null;                           -- aufgegeben: kein Start mehr für diesen Plan
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  hart := public.prophos_gegenrichtung_frei(new.id, new.richtung);
  if coalesce((hart->>'frei')::boolean, true) = false then
    ziel := now() + make_interval(secs => 300 + floor(random() * 3300));
    txt := k || ': dein Konto ' || coalesce(hart->>'grund', 'läuft dort in Gegenrichtung');
    n := coalesce((old.mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1;
    if cfd then
      -- erst nur aus derselben Sperr-Kette (wie Waage-Deckel D′): wartet, naechster = jetzige Startzeit, ≤ 24 h — sonst beginnt eine neue Kette
      erst := case when ss->>'art' = 'richtung' and ss->>'status' = 'wartet' and (ss->>'erst') is not null and (ss->>'naechster') is not null
                         and old.start_um is not null and (ss->>'naechster')::timestamptz = old.start_um
                         and (ss->>'erst')::timestamptz > now() - interval '24 hours'
                   then (ss->>'erst')::timestamptz else coalesce(old.start_um, now()) end;
      ende := public.prophos_cfd_fenster_ende(erst);
      if ziel > ende then
        txt := 'Riegel: Gegenrichtung Schwesterkonto — nicht gestartet (' || txt || '; Startfenster endete '
               || to_char(ende at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai, Versuch ' || n || ')';
        update public.trade_plans set
               mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
                 'art', 'richtung', 'status', 'aufgegeben', 'text', txt, 'at', now(), 'erst', erst, 'ende', ende, 'versuche', n, 'start', old.start_um))
         where id = new.id;
        insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
        values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um, '[Gegenrichtung gleiche ID] ' || txt, 'start');
        return null;
      end if;
    end if;
    if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
      update public.trade_plans set start_um = ziel,
             mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'richtung', 'text', txt, 'at', now(), 'naechster', ziel, 'versuche', n)
               || case when cfd then jsonb_build_object('status', 'wartet', 'erst', erst, 'ende', ende) else '{}'::jsonb end)
       where id = new.id;
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
              '[Gegenrichtung gleiche ID] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
    end if;
    return null;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  select * into c from public.prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()));
  if c.ziel is null then
    return new;
  end if;
  ziel := c.ziel + make_interval(secs => 20 + floor(random() * 20));
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    txt := k || ': ' || case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '
                             else 'eine andere ID ' end || c.grund;
    update public.trade_plans set start_um = ziel,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'richtung', 'text', txt, 'at', now(), 'naechster', ziel,
             'versuche', coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1))
     where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            case when c.grund like '%gegen den laufenden Trade gesperrt%' then '[Gegenrichtung gleiche ID] ' else '[Gegenhedge 90 s] ' end
            || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'),
            'start');
  end if;
  return null;
end $function$;

revoke all on function public.prophos_cfd_fenster_ende(timestamptz) from public, anon, authenticated;
grant execute on function public.prophos_cfd_fenster_ende(timestamptz) to service_role;

-- Proben (SQL-Editor, nur lesen):
-- select public.prophos_cfd_fenster_ende('2026-11-04 02:25:00+00');   -- erst 06:25 Dubai → 18:00 Dubai (cfd_bis) = 14:00 UTC
-- select public.prophos_cfd_fenster_ende('2026-11-04 21:32:00+00');   -- 01:32 Dubai, außerhalb des Fensters → erst + 60 min, höchstens dt-Tagesgrenze

-- START-SPERRE SICHTBAR (13.10.2026, Finn nach Emins zwei Tradeify-Longs, die 7× um ~10 min geschoben wurden und nie starteten:
-- „Bitte in Zukunft dann hinschreiben als Feedback-Meldung: Ah, okay, die Order ging nicht durch wegen dem Richtungsschutz").
-- Die Gegenrichtungs-Sperre schrieb ihren Grund nur in auto_plan_umplanung (kein Lese-Recht für die Tabs). Jetzt legt sie ihn zusätzlich
-- an den Plan: trade_plans.mt5_baseline.start_sperre = {art:'richtung', text, at, naechster, versuche}. Der PC-Tab liest den Plan nach
-- dem abgelehnten Claim ohnehin frisch (suClaimFehlgriff) → Toast + Chip auf der Karte. Logik der Sperre unverändert.

CREATE OR REPLACE FUNCTION public.trade_plans_gegenhedge()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  k text;
  c record;
  ziel timestamptz;
  hart jsonb;
  txt text;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  hart := public.prophos_gegenrichtung_frei(new.id, new.richtung);
  if coalesce((hart->>'frei')::boolean, true) = false then
    perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
    ziel := now() + interval '10 minutes' + make_interval(secs => 20 + floor(random() * 20));
    if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
      txt := k || ': dein Konto ' || coalesce(hart->>'grund', 'läuft dort in Gegenrichtung');
      update public.trade_plans set start_um = ziel,
             mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'richtung', 'text', txt, 'at', now(), 'naechster', ziel,
               'versuche', coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1))
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
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
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

-- RIEGEL-LOCK (30.10.2026, Crosscheck Richtungsschutz S5, Punkt 3/4; Auftrag Master). Zwei Lücken im harten Gegenrichtungs-Riegel je ID × Firma:
--  (1) trade_plans_gegenhedge (Claim) rief prophos_gegenrichtung_frei VOR dem Advisory-Lock auf. Zwei gleichzeitige Claims in Gegenrichtung
--      sahen sich dort nicht; den Rest fing nur der gelockte 90-s-Teil — und den überspringt ein > 60 min überfälliger Plan (return new vor
--      dem Lock). Jetzt: Lock IMMER ZUERST (unabhängig vom Alter), dann die harte Prüfung, dann wie bisher die 60-min-Ausnahme nur für den
--      weichen 90-s-Teil (prophos_gegenhedge_konflikt). Rest Wort für Wort die Live-Fassung (sql/2026-10-13_start_sperre_meldung.sql).
--  (2) Hand-Starts ohne Claim (Popup/„Jetzt starten") laufen nie durch den Claim-Trigger. Neu: trade_plans_gegenrichtung_start BEFORE UPDATE
--      OF started_at (null → gesetzt): dieselbe harte Prüfung unter demselben Lock. Die Order liegt dann schon beim Broker — der Trigger
--      BLOCKIERT NICHT (sonst fehlte der laufende Trade in der DB), er schreibt mt5_baseline.richtung_verstoss {at, grund, firma} an den Plan;
--      Railway (alarm_tick) meldet daraus 🔴 „Gegenrichtung gestartet" einmal je Plan.
-- 72-h-Grenze in prophos_gegenrichtung_frei bleibt unverändert (Finns Wort offen). Wiederholbar.
-- Rückbau: (1) sql/2026-10-13_start_sperre_meldung.sql erneut einspielen; (2) drop trigger trade_plans_gegenrichtung_start on public.trade_plans.

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
  -- RIEGEL-LOCK (30.10.2026): Lock vor jeder Prüfung — zwei gleichzeitige Claims derselben Firma sehen sich jetzt auch in der harten Prüfung
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  hart := public.prophos_gegenrichtung_frei(new.id, new.richtung);
  if coalesce((hart->>'frei')::boolean, true) = false then
    ziel := now() + make_interval(secs => 300 + floor(random() * 3300));
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
  -- > 60 min überfällig: nur der weiche 90-s-Teil entfällt (wie bisher) — die harte Prüfung oben lief schon unter dem Lock
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

CREATE OR REPLACE FUNCTION public.trade_plans_gegenrichtung_start()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  k text;
  hart jsonb;
begin
  -- Hand-Start ohne Claim (30.10.2026): nicht blockieren (Order ist schon gesendet), nur festhalten → 🔴 über Railway (alarm_tick)
  if coalesce(btrim(new.master_firm), '') = '' or new.richtung not in ('buy', 'sell') then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  hart := public.prophos_gegenrichtung_frei(new.id, new.richtung);
  if coalesce((hart->>'frei')::boolean, true) = false then
    new.mt5_baseline := coalesce(new.mt5_baseline, '{}'::jsonb) || jsonb_build_object('richtung_verstoss', jsonb_build_object(
      'at', now(), 'firma', k, 'richtung', new.richtung, 'grund', left(coalesce(hart->>'grund', 'Gegenrichtung derselben ID × Firma läuft'), 300)));
  end if;
  return new;
exception when others then
  -- nie einen echten Start an der Prüfung scheitern lassen; Grund am Plan
  new.mt5_baseline := coalesce(new.mt5_baseline, '{}'::jsonb) || jsonb_build_object('richtung_verstoss', jsonb_build_object(
    'at', now(), 'firma', k, 'richtung', new.richtung, 'grund', 'Prüfung beim Start fehlgeschlagen: ' || left(sqlerrm, 200), 'unklar', true));
  return new;
end $function$;

drop trigger if exists trade_plans_gegenrichtung_start on public.trade_plans;
create trigger trade_plans_gegenrichtung_start
  before update of started_at on public.trade_plans
  for each row when (old.started_at is null and new.started_at is not null)
  execute function public.trade_plans_gegenrichtung_start();

-- Probe (nur lesen): Pläne mit Verstoß der letzten 7 Tage
-- select id, user_id, master_firm, richtung, started_at, mt5_baseline->'richtung_verstoss' from public.trade_plans
--  where mt5_baseline ? 'richtung_verstoss' and started_at > now() - interval '7 days';

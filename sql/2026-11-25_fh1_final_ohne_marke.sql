-- 2026-11-25 — FH1 Finaler Futures-Trade nie ohne Hedge-Kennung starten (Master 25.11.2026, Befund + Vorgabe Prüfer S2, S3-Review).
-- Lücke: trade_plans_a_final_halten (BEFORE UPDATE OF start_um_gestartet_at = Claim) prüft zuerst prophos_final_hedge_firma(firma, hedge_art). Für
-- Lucid (und künftig FundedNext Futures) ist das nur mit hedge_art 'tradeify_final' wahr, sonst `return new` → Start; trade_plans_a0_hedge_freigabe greift
-- nur bei hedge_art apex/tradeify_final, trade_plans_ein_finaler ebenso über prophos_final_hedge_firma. Die Marke setzt allein Railway tfh_tick (60 s).
-- Fälle: (a) Railway/tfh_tick steht, (b) Gruppen-Modelle nicht lesbar → tfh_tick lässt Lucid/FNF aus, (c) Plan wird durch neue tv_balance final und
-- < 60 s später geclaimt → finaler Plan ohne Marke startet OHNE Hedge. Tradeify war sicher (Firma zählt ohne Marke), wurde aber gleich +1 Tag geschoben.
-- Fix (nur DB, deckt jeden Claim-Weg — PC-Tab, Puls, Hand-Start —, weil alle über start_um_gestartet_at laufen):
--   1. prophos_final_hedge_kandidat(firma, user_id): Hedge-Weg an (prophos_tradeify_final_hedge_an), Firma in prophos_final_hedge_firmen()
--      (regeln.tradeify_final_hedge.firmen — heute Tradeify + Lucid, FNF sobald dort eingetragen), user_id NICHT in einer Verwalter-Gruppe mit
--      auto_plan_gruppe-Zeile (Emin: Gruppen-Planer, orbit_prio2 → ah_tick) und kein Firmen-Modell orbit_prio2 in regeln.firmen.
--   2. trade_plans_a_final_halten: finaler Plan (prophos_plan_final — dieselbe Regel wie tfh_ist_final, keine zweite Final-Erkennung) ohne Marke
--      (hedge_art leer, kein tradeify_hedge, kein apex_hedge-Status), tvv2 + auto_plan, kein Winning Day, Kandidat → nur kurz zurückstellen
--      (+2–4 min gestreut, start_sperre art 'hedge_marke' „wartet auf Hedge-Kennung“), nie +1 Tag und nie Start. Dann markiert tfh_tick, danach
--      greifen Freigabe, ein finaler je ID und Halten wie gewohnt. Steht der Takt (a/b), wird alle 2–4 min erneut zurückgestellt — nie ohne Hedge;
--      nach 30 min ohne Kennung einmal ein Eintrag „Railway tfh_tick prüfen“ in auto_plan_umplanung (Review-Fund: sonst lief das still).
--      Derselbe Plan mit tradeify_hedge, aber ohne Marke (tfh_tick „ohne Hedge“), fällt in den bisherigen Tages-Halt (nie Start ohne Orbit V3 + Hedge).
--   Alles andere bitgleich (Firmen-Regel, Orbit-V3-Durchlass, Mehrfach-Claim-Schutz, Tages-Halt mit Text). Emins orbit_prio2, Tradeify CFD, Hand-
--   und Winning-Day-Pläne bleiben unberührt; Hedge-Weg aus (an=false): nie Kandidat → wie bisher.
-- Beleg 25.11.2026 (14 Tage, finale Tradeify/Lucid-Pläne nach prophos_plan_final): kein HT-Auto-Plan lief ohne Hedge (Lucid 23 + Tradeify 4 mit
-- Final-Hedge-Marke); 6 HT-Hand-Finals mit Orbit V3 ohne Marke; 1 Emin-Hand-Plan Lucid 50k ohne Hedge (Gruppe Emin, nicht dieser Weg).
-- NICHT EINGESPIELT — Ausführen nur auf Finns/Masters Wort, nicht von einem Slave. Wiederholbar. Rückbau: unten.

begin;

do $pruef$
begin
  perform 'public.prophos_final_hedge_firma(text, text)'::regprocedure;
  perform 'public.prophos_final_hedge_firmen()'::regprocedure;
  perform 'public.prophos_tradeify_final_hedge_an()'::regprocedure;
  perform 'public.prophos_tradeify_final_halten_an()'::regprocedure;
  perform 'public.prophos_plan_final(uuid)'::regprocedure;
  perform 'public.prophos_firma_key(text)'::regprocedure;
exception when undefined_function then
  raise exception 'FH1: Grundfunktionen fehlen (sql/2026-10-29_tradeify_final_hedge.sql, sql/2026-11-06_lucid_final_hedge.sql)';
end $pruef$;

-- ── 1. Kandidat für den Final-Hedge-Weg (Vorgabe S2, wie tfh_plan_dabei) ─────────────────────────────────────────────────
create or replace function public.prophos_final_hedge_kandidat(p_firm text, p_user uuid)
returns boolean
language plpgsql stable security definer set search_path = public as $$
declare
  k text := public.prophos_firma_key(p_firm);
  n text := regexp_replace(lower(coalesce(p_firm, '')), '[^a-z0-9]', '', 'g');
begin
  if k is null or not public.prophos_tradeify_final_hedge_an() then
    return false;
  end if;
  if not (k = any(public.prophos_final_hedge_firmen())) or p_user is null then
    return false;
  end if;
  -- nicht in einer Verwalter-Gruppe mit Gruppen-Planer (auto_plan_gruppe-Zeile) — Mitglied oder Verwalter (Prüfer S2)
  if exists (select 1 from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
              where m.user_id = p_user and g.verwalter_user_id is not null
                and exists (select 1 from public.auto_plan_gruppe apg where apg.gruppe_id = g.id))
     or exists (select 1 from public.id_gruppen g where g.verwalter_user_id = p_user
                and exists (select 1 from public.auto_plan_gruppe apg where apg.gruppe_id = g.id)) then
    return false;
  end if;
  -- nie mit Firmen-Modell Orbit Prio 2 (ein Hedge je Plan — der gehört dann ah_tick)
  if exists (select 1 from public.auto_plan_regeln r, jsonb_array_elements(case when jsonb_typeof(r.regeln->'firmen') = 'array' then r.regeln->'firmen' else '[]'::jsonb end) f
              where r.id = 1 and f->>'modell' = 'orbit_prio2'
                and exists (select 1 from jsonb_array_elements_text(case when jsonb_typeof(f->'namen') = 'array' then f->'namen' else '[]'::jsonb end) x
                             where x <> '' and (n = x or n like x || '%'))) then
    return false;
  end if;
  return true;
end $$;
revoke all on function public.prophos_final_hedge_kandidat(text, uuid) from public, anon, authenticated;

-- ── 2. Halte-Riegel: ohne Marke nur kurz zurückstellen ─────────────────────────────────────────────────────────────
create or replace function public.trade_plans_a_final_halten()
returns trigger
language plpgsql security definer set search_path = public as $function$
declare
  ziel timestamptz;
  txt text;
  ss jsonb;
  weg boolean;
  kand boolean;
  erst boolean;
  lange boolean;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  -- FH1: gehört dem Final-Hedge-Weg (tfh_plan_dabei), auch ohne Marke — außer der Plan ist schon Orbit Prio 2 (Marke 'apex', ah_tick)
  -- nur tvv2-Auto-Pläne ohne Winning Day (wie tfh_tick: „finaler Futures-Auto-Plan“) — Hand- und WD-Pläne bleiben bitgleich
  weg := coalesce(new.auto_plan, false) and coalesce(new.route, '') = 'tvv2' and not coalesce(new.winning_day, false)
         and coalesce(new.mt5_baseline->>'hedge_art', '') <> 'apex'
         and coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = ''
         and public.prophos_final_hedge_kandidat(new.master_firm, new.user_id);
  -- … und tfh_tick hat noch gar nicht entschieden (keine Marke, kein tradeify_hedge) → kurz halten statt einen Tag
  kand := weg and coalesce(new.mt5_baseline->>'hedge_art', '') = '' and new.mt5_baseline->'tradeify_hedge' is null;
  if not (public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art') or weg) then
    return new;
  end if;
  if coalesce(new.orbit_v3, false) and coalesce(new.hedge_eur, 0) > 0 and public.prophos_tradeify_final_hedge_an() then
    return new;
  end if;
  if not (public.prophos_tradeify_final_halten_an() or public.prophos_tradeify_final_hedge_an()) or not public.prophos_plan_final(new.id) then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if kand then
    if ss->>'art' = 'hedge_marke' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
      return null;                                 -- Mehrfach-Claim gleich nach dem Zurückstellen
    end if;
    erst := coalesce(ss->>'art', '') <> 'hedge_marke';
    lange := not erst and ss->>'erst_at' is not null and (ss->>'erst_at')::timestamptz < now() - interval '30 minutes';
    ziel := greatest(coalesce(old.start_um, now()), now()) + interval '2 minutes' + make_interval(secs => floor(random() * 120));
    txt := 'finaler ' || public.prophos_firma_key(new.master_firm) || '-Trade wartet auf Hedge-Kennung (Railway-Takt) — startet nie ohne Gegenhedge';
    update public.trade_plans
       set start_um = ziel,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'hedge_marke', 'text', txt, 'at', now(), 'naechster', ziel,
             'erst_at', case when erst then to_jsonb(now()) else coalesce(ss->'erst_at', to_jsonb(now())) end,
             'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end,
             'lange', case when erst then false else lange or coalesce(ss->>'lange', '') = 'true' end))
     where id = new.id;
    if erst then
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
              '[finaler ' || public.prophos_firma_key(new.master_firm) || ' ohne Hedge-Kennung] ' || txt || ' — neuer Versuch '
              || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
    elsif lange and coalesce(ss->>'lange', '') <> 'true' then
      -- Review: steht der Takt (Railway aus, Gruppen-Modelle nicht lesbar), einmal sichtbar melden — weiter nie Start ohne Hedge
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
              '[finaler ' || public.prophos_firma_key(new.master_firm) || ' seit 30 min ohne Hedge-Kennung] Railway tfh_tick prüfen — der Plan wird weiter '
              || 'alle 2–4 min zurückgestellt und startet nie ohne Gegenhedge', 'start');
    end if;
    return null;
  end if;
  if ss->>'art' = 'final_halten' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;
  end if;
  ziel := greatest(coalesce(old.start_um, now()), now() - interval '12 hours') + interval '1 day'
          + make_interval(secs => floor(random() * 1200));
  if ziel < now() + interval '12 hours' then
    ziel := now() + interval '1 day' + make_interval(secs => floor(random() * 1200));
  end if;
  txt := 'finaler ' || public.prophos_firma_key(new.master_firm) || '-Trade wartet auf Gegenhedge (TP ' || coalesce(round(new.master_tp)::text, '?') || ' $'
         || coalesce(', ' || nullif(new.mt5_baseline->'tradeify_hedge'->>'grund', ''), '') || ')';
  update public.trade_plans
     set start_um = ziel,
         hand_werte_at = coalesce(hand_werte_at, now()),
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'final_halten', 'text', txt, 'at', now(), 'naechster', ziel,
           'versuche', case when mt5_baseline->'start_sperre'->>'art' = 'final_halten'
                            then coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1 else 1 end))
   where id = new.id;
  insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
  values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
          '[finaler ' || public.prophos_firma_key(new.master_firm) || ' gehalten] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'DD.MM. HH24:MI'), 'start');
  return null;
end $function$;

commit;

-- Prüfen (nur lesen):
--   select public.prophos_final_hedge_kandidat('Lucid Trading', '<HT-ID>'), public.prophos_final_hedge_kandidat('Lucid Trading', '<Emin-ID>'),
--          public.prophos_final_hedge_kandidat('Tradeify', '<Emin-ID>'), public.prophos_final_hedge_kandidat('Tradeify CFD', '<HT-ID>');   -- t, f, f, f
--
-- Rückbau (Stand vor FH1, live 25.11.2026):
--   drop function public.prophos_final_hedge_kandidat(text, uuid);   -- erst NACH dem Zurückspielen der Funktion unten
--   trade_plans_a_final_halten wie in sql/2026-11-06_lucid_final_hedge.sql (Stand nach dem LF1-Patch): ohne weg/kand/hedge_marke-Block,
--   Firmen-Prüfung nur „if not public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art') then return new;“.

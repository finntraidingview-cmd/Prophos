-- EIN FINALER TRADEIFY-TRADE JE ID (Finn 21.10.2026 ~23:45 Dubai, über Master: „Bei Aurel sind grad 3 Accounts bei Tradeify 1 vor Pass.
-- Ich will eine Regel: dass bei den Tradeify finalen Trades immer nur 1 gleichzeitig pro ID gemacht werden kann, nicht dass dann bei
-- Aurel alle 3 gleichzeitig starten und alle blowen.")
--
-- Lage: Aurel …7608 / …4872 / …9050 stehen um 156.950, Ziel 159.000 — der nächste Trade ist bei allen dreien der letzte. Bisher galt nur
-- Firmen-Abstand 1 min (andere IDs) und keine Gegenrichtung je ID × Firma; GLEICHE Richtung durfte parallel laufen. Läuft der Markt
-- gegen alle drei, sind alle drei weg (Tradeify-Liq ohne SL).
--
-- Regel (DB-seitig, Railway hängt auf .1684 — Backend-Änderungen wären nicht live):
--   Je ID × Firma aus prophos_ein_finaler_firmen() (nur Tradeify) höchstens EIN finaler Trade, der läuft oder geclaimt ist.
--   „läuft" wie der Gegenrichtungs-Riegel (prophos_gegenrichtung_frei_konto): status open, oder review ohne Endlesung
--   (prophos_plan_gelesen) — 72 h; „geclaimt" = planned, ungestartet, Claim/Orbit-Sendung < 10 min her.
--   Final (EINE Stelle, prophos_plan_final): Auto-Planer-Stufe „letzter Trade" oder „Klein-Trade"; sonst TP ≥ Rest aus der Notiz
--   („Rest 2.050 $ bis Ziel", auch nach ✎-Hand-Änderung des TP); Hand-Pläne ohne Notiz: TP ≥ ziel_usd − tv_balance des Kontos.
--   Tage-Mini („Tage sammeln") ist nie final.
--   Ein zweiter finaler Claim derselben ID × Firma scheitert (return null), start_um + 10–20 min gewürfelt (Jitter-Regel), Grund an den
--   Plan (mt5_baseline.start_sperre art 'ein_finaler') und ins Protokoll auto_plan_umplanung „[ein finaler Tradeify je ID] …".
--   Normale Etappen, andere IDs und andere Firmen bleiben unberührt.
-- Schalter je Firma: prophos_ein_finaler_firmen() — Firma dazu = Funktion neu anlegen (Schlüssel wie prophos_firma_key).
-- Lese-RPC prophos_ein_finaler_frei(p_plan) fragt der PC-Tab vor jedem Orbit-V2-Start (auch Hand-Start/Neu starten ohne Claim).
--
-- Reihenfolge: BEFORE-Trigger feuern alphabetisch — trade_plans_big_trade, trade_plans_ein_finaler, trade_plans_firmen_abstand,
-- trade_plans_gegenhedge. Sperrt einer (return null), laufen die übrigen für diesen Claim nicht.
--
-- RÜCKBAU (komplett, nichts sonst hängt daran):
--   drop trigger if exists trade_plans_ein_finaler on public.trade_plans;
--   drop function if exists public.trade_plans_ein_finaler();
--   drop function if exists public.prophos_ein_finaler_frei(uuid);
--   drop function if exists public.prophos_plan_final(uuid);
--   drop function if exists public.prophos_plan_final_text(text, numeric);
--   drop function if exists public.prophos_ein_finaler_firmen();
-- Nur abschalten (Funktionen bleiben, Tab sieht „frei"): Schalter leeren —
--   create or replace function public.prophos_ein_finaler_firmen() returns text[] language sql immutable as $f$ select array[]::text[] $f$;

do $pruef$
begin
  perform 'public.prophos_firma_key(text)'::regprocedure;
  perform 'public.prophos_plan_gelesen(uuid)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-19_gegenrichtung_review_gelesen.sql einspielen (prophos_plan_gelesen fehlt)';
end $pruef$;

-- ── 1. Schalter je Firma ───────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.prophos_ein_finaler_firmen()
returns text[]
language sql immutable as $$
  select array[public.prophos_firma_key('Tradeify')]
$$;

-- ── 2. Final-Erkennung (rein, testbar): Notiz + TP ─────────────────────────────────────────────────────────────────────
-- Notiz-Formate (DB 21.10.2026): „Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)",
-- „Auto-Planer · Klein-Trade · Rest 84 $ · …", „Auto-Planer · Etappe · Rest 5.472 $ bis Ziel · …", „Auto-Planer · Tage sammeln 3/5 · …".
-- Zahlen deutsch: Punkt = Tausender, Komma = Dezimal. -> true | false | null (aus der Notiz nicht erkennbar)
create or replace function public.prophos_plan_final_text(p_notes text, p_tp numeric)
returns boolean
language plpgsql immutable as $$
declare
  n text := coalesce(p_notes, '');
  r text;
  rest numeric;
begin
  if n ~ 'Auto-Planer · Tage sammeln' then
    return false;
  end if;
  if n ~ 'Auto-Planer · (letzter Trade|Klein-Trade)' then
    return true;
  end if;
  r := substring(n from 'Rest ([0-9][0-9.]*(,[0-9]+)?) \$ bis Ziel');
  if r is null then
    return null;
  end if;
  rest := replace(replace(r, '.', ''), ',', '.')::numeric;
  if rest <= 0 then
    return true;   -- Ziel schon erreicht laut Notiz: jeder Trade wäre der letzte
  end if;
  return coalesce(p_tp, 0) > 0 and p_tp >= rest;
end $$;

-- Plan-Ebene: Notiz zuerst, sonst Konto (ziel_usd − tv_balance) — Hand-Pläne ohne Auto-Planer-Notiz
create or replace function public.prophos_plan_final(p_plan uuid)
returns boolean
language plpgsql stable security definer set search_path = public as $$
declare
  p record;
  f boolean;
begin
  select tp.notes, tp.master_tp, a.ziel_usd, a.tv_balance
    into p
    from public.trade_plans tp left join public.accounts a on a.id = tp.master_account_id
   where tp.id = p_plan;
  if not found then
    return false;
  end if;
  f := public.prophos_plan_final_text(p.notes, p.master_tp);
  if f is not null then
    return f;
  end if;
  if p.ziel_usd is not null and p.tv_balance is not null and coalesce(p.master_tp, 0) > 0 then
    return p.master_tp >= p.ziel_usd - p.tv_balance;
  end if;
  return false;
end $$;
grant execute on function public.prophos_plan_final(uuid) to authenticated, service_role;

-- ── 3. Leseprüfung (Trigger + PC-Tab) ──────────────────────────────────────────────────────────────────────────────────
-- -> {frei, grund?, plan?, firma}; frei=true auch, wenn die Regel für den Plan nicht gilt (andere Firma, nicht final)
create or replace function public.prophos_ein_finaler_frei(p_plan uuid)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  pl record;
  k text;
  g record;
begin
  select id, user_id, master_firm, status into pl from public.trade_plans where id = p_plan;
  if not found then
    return jsonb_build_object('frei', true, 'grund', 'Plan unbekannt');
  end if;
  k := public.prophos_firma_key(pl.master_firm);
  if pl.user_id is null or k is null or not (k = any(public.prophos_ein_finaler_firmen())) then
    return jsonb_build_object('frei', true, 'firma', k, 'grund', 'Regel gilt für diese Firma nicht');
  end if;
  if not public.prophos_plan_final(pl.id) then
    return jsonb_build_object('frei', true, 'firma', k, 'grund', 'kein finaler Trade');
  end if;
  select p.id, p.master_name, p.status,
         coalesce(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at, p.created_at) as seit
    into g
    from public.trade_plans p
   where p.id <> pl.id
     and p.user_id = pl.user_id
     and public.prophos_firma_key(p.master_firm) = k
     and (
           (p.status in ('open', 'review')
            and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))
            and coalesce(p.started_at, p.start_um_gestartet_at, p.orbit_gesendet_at, p.created_at) > now() - interval '72 hours')
        or (p.status = 'planned' and p.started_at is null
            and coalesce(p.orbit_gesendet_at, p.start_um_gestartet_at) > now() - interval '10 minutes')
         )
     and public.prophos_plan_final(p.id)
   order by 4 desc
   limit 1;
  if g.id is null then
    return jsonb_build_object('frei', true, 'firma', k);
  end if;
  return jsonb_build_object('frei', false, 'firma', k, 'plan', g.id,
    'grund', '„' || coalesce(g.master_name, 'Konto') || '“ '
             || case g.status when 'review' then 'ist als finaler Trade zu Ende, aber noch nicht gelesen'
                              when 'planned' then 'startet gerade als finaler Trade'
                              else 'läuft als finaler Trade' end
             || coalesce(' (seit ' || to_char(g.seit at time zone 'Asia/Dubai', 'HH24:MI') || ' Dubai)', '')
             || ' — je ID nur ein finaler ' || k || '-Trade gleichzeitig');
end $$;
grant execute on function public.prophos_ein_finaler_frei(uuid) to authenticated, service_role;

-- ── 4. Claim-Trigger ───────────────────────────────────────────────────────────────────────────────────────────────────
-- Hart, auch beim „verpasst"-Claim (start_um älter als 60 min) — wie die Gegenrichtung. Advisory-Lock je ID × Firma: zwei finale
-- Claims derselben ID im selben Moment laufen nacheinander, der zweite sieht den ersten (READ COMMITTED, Prüfung NACH dem Lock).
create or replace function public.trade_plans_ein_finaler()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  frei jsonb;
  ziel timestamptz;
  txt text;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  if k is null or not (k = any(public.prophos_ein_finaler_firmen())) then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtext('prophos_ein_finaler:' || new.user_id::text || ':' || k));
  frei := public.prophos_ein_finaler_frei(new.id);
  if coalesce((frei->>'frei')::boolean, true) then
    return new;
  end if;
  -- Jitter-Regel: gewürfelt 10–20 min, nie ein fester Takt
  ziel := now() + interval '10 minutes' + make_interval(secs => floor(random() * 600));
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    txt := k || ': ' || coalesce(frei->>'grund', 'ein anderer finaler Trade läuft');
    update public.trade_plans set start_um = ziel,
           mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
             'art', 'ein_finaler', 'text', txt, 'at', now(), 'naechster', ziel, 'plan', frei->>'plan',
             'versuche', coalesce((mt5_baseline->'start_sperre'->>'versuche')::int, 0) + 1))
     where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[ein finaler Tradeify je ID] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS'), 'start');
  end if;
  return null;
end $$;

drop trigger if exists trade_plans_ein_finaler on public.trade_plans;
create trigger trade_plans_ein_finaler
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_ein_finaler();

-- ── PROBE (einzeln ausführen, endet mit ROLLBACK — ändert nichts) ──────────────────────────────────────────────────────
-- begin;
--   -- reine Erkennung
--   select public.prophos_plan_final_text('Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)', 2300) as letzter,      -- true
--          public.prophos_plan_final_text('Auto-Planer · Etappe · Rest 5.472 $ bis Ziel · Balance 153.528 (TV)', 3532) as etappe,                            -- false
--          public.prophos_plan_final_text('Auto-Planer · Etappe · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)', 2100) as etappe_tp_reicht,                  -- true
--          public.prophos_plan_final_text('Auto-Planer · Tage sammeln 3/5 · Mini-Trade 0,01 Lot', 50) as mini,                                                -- false
--          public.prophos_plan_final_text(null, 15000) as hand;                                                                                               -- null
--   -- zwei finale Tradeify-Pläne derselben ID: der erste claimt, der zweite wird verschoben
--   with u as (select user_id, master_account_id, master_firm, master_name from public.trade_plans where public.prophos_firma_key(master_firm) = 'Tradeify' and notes like 'Auto-Planer · Etappe%' and master_account_id is not null order by created_at desc limit 1)
--   insert into public.trade_plans (id, user_id, master_account_id, master_firm, master_name, richtung, status, route, master_tp, notes, start_um)
--   select x.id, u.user_id, u.master_account_id, u.master_firm, 'PROBE ' || x.n, 'buy', 'planned', 'tvv2', 2300,
--          'Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.050 $ bis Ziel · Balance 156.950 (TV)', now()
--     from u, (values ('00000000-0000-0000-0000-0000000f1a01'::uuid, 'A'), ('00000000-0000-0000-0000-0000000f1a02'::uuid, 'B')) x(id, n);
--   update public.trade_plans set start_um_gestartet_at = now() where id = '00000000-0000-0000-0000-0000000f1a01' and start_um_gestartet_at is null;   -- UPDATE 1
--   update public.trade_plans set start_um_gestartet_at = now() where id = '00000000-0000-0000-0000-0000000f1a02' and start_um_gestartet_at is null;   -- UPDATE 0
--   select id, start_um_gestartet_at, start_um, mt5_baseline->'start_sperre' from public.trade_plans where id in ('00000000-0000-0000-0000-0000000f1a01', '00000000-0000-0000-0000-0000000f1a02');
--   select public.prophos_ein_finaler_frei('00000000-0000-0000-0000-0000000f1a02');   -- frei false, grund „PROBE A“ startet gerade …
-- rollback;

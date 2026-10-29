-- FINALER TRADEIFY HALTEN (Finn 29.10.2026 ~16:05 Dubai, über Master „TRADEIFY-FINAL-HALTEN"): finale Tradeify-Trades — TP erreicht oder
-- überschreitet das Ziel (z. B. Stand 157k + TP ≥ 159k) — starten nicht mehr, bis die Gegenhedge-Logik für den letzten Trade gebaut ist.
-- Sie verfallen nicht und werden nicht gelöscht. Nur Tradeify Futures (Schlüssel prophos_firma_key('Tradeify'); Tradeify CFD hat einen
-- eigenen Schlüssel, sql/2026-10-23_tradeify_cfd_firma_key.sql), alle anderen Firmen und nicht-finalen Tradeify-Trades laufen weiter.
--
-- (1) Schalter auto_plan_regeln.regeln.tradeify_final_halten = true (Railway-Planer ap_planen plant dann keinen finalen Tradeify-Trade,
--     Grund „finaler Tradeify-Trade wartet auf Gegenhedge"; fehlt der Schlüssel, gilt AN).
-- (2) Netz am Claim (BEFORE UPDATE OF start_um_gestartet_at, wie trade_plans_ein_finaler): finaler Tradeify-Plan (prophos_plan_final) bei
--     Schalter an → Claim scheitert (return null), der Plan bleibt planned; start_um rückt einen Tag weiter (+ 0–20 min gestreut,
--     Jitter-Regel — Nachtlauf/Tages-Reset räumen nur Pläne mit Start in der Vergangenheit weg), hand_werte_at gesetzt (Neuplanen und
--     Balance-Wache löschen solche Pläne nie), Grund an den Plan (mt5_baseline.start_sperre art 'final_halten' → ⚪ einmal über alarm_tick)
--     und ins Protokoll auto_plan_umplanung. Name mit „a_", damit er vor den übrigen Claim-Triggern (alphabetisch) feuert.
--     Ein Start von Hand ohne Claim bleibt möglich (Finns Entscheidung).
--
-- Abschalten (Pläne starten wieder beim nächsten Claim):
--   update public.auto_plan_regeln set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{tradeify_final_halten}', 'false'::jsonb) where id = 1;
-- RÜCKBAU komplett:
--   drop trigger if exists trade_plans_a_final_halten on public.trade_plans;
--   drop function if exists public.trade_plans_a_final_halten();
--   drop function if exists public.prophos_tradeify_final_halten_an();

do $pruef$
begin
  perform 'public.prophos_firma_key(text)'::regprocedure;
  perform 'public.prophos_plan_final(uuid)'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-21_tradeify_ein_finaler_je_id.sql einspielen (prophos_plan_final fehlt)';
end $pruef$;

-- ── 1. Schalter ────────────────────────────────────────────────────────────────────────────────────────────────────────
update public.auto_plan_regeln
   set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{tradeify_final_halten}', 'true'::jsonb)
 where id = 1;

create or replace function public.prophos_tradeify_final_halten_an()
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select (regeln->>'tradeify_final_halten')::boolean from public.auto_plan_regeln where id = 1), true)
$$;
grant execute on function public.prophos_tradeify_final_halten_an() to authenticated, service_role;

-- ── 2. Claim-Trigger ───────────────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.trade_plans_a_final_halten()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ziel timestamptz;
  txt text;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if public.prophos_firma_key(new.master_firm) is distinct from public.prophos_firma_key('Tradeify') then
    return new;   -- nur Tradeify Futures (Tradeify CFD hat einen eigenen Schlüssel)
  end if;
  if not public.prophos_tradeify_final_halten_an() or not public.prophos_plan_final(new.id) then
    return new;
  end if;
  -- einen Tag weiter, vom geplanten Start aus (liegt er weit zurück, von jetzt), gestreut 0–20 min
  ziel := greatest(coalesce(old.start_um, now()), now() - interval '12 hours') + interval '1 day'
          + make_interval(secs => floor(random() * 1200));
  if ziel < now() + interval '12 hours' then
    ziel := now() + interval '1 day' + make_interval(secs => floor(random() * 1200));
  end if;
  txt := 'finaler Tradeify-Trade wartet auf Gegenhedge (TP ' || coalesce(round(new.master_tp)::text, '?') || ' $)';
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
          '[finaler Tradeify gehalten] ' || txt || ' — Start frühestens ' || to_char(ziel at time zone 'Asia/Dubai', 'DD.MM. HH24:MI'), 'start');
  return null;
end $$;

drop trigger if exists trade_plans_a_final_halten on public.trade_plans;
create trigger trade_plans_a_final_halten
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_a_final_halten();

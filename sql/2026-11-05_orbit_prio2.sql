-- ORBIT PRIO 2 je Firma und Gruppe (MO1, 05.11.2026, Finn ~10:00 Dubai: „ja bau ma“) — NICHT automatisch einspielen, Finn/Master spielt ein.
--
-- Der Apex-Challenge-Weg (Railway ah_tick: Marke mt5_baseline.hedge_art = 'apex', Umstellen auf den Winning-Day-Weg mit Fusion-Gegenhedge, Riegel
-- trade_plans_a1_apex_hedge) heißt jetzt „Orbit Prio 2“ und ist je Firma wählbar (app.py ap_firma_modell):
--   HT     = auto_plan_regeln.regeln.firmen[].modell  (Einstellungen → Challenge-Planer → Futures → Firma → „Modell“, POST /admin/auto-plan/modell)
--   Gruppe = auto_plan_gruppe.firmen_modell {Firmen-Schlüssel namen[0]: 'orbit_v2' | 'orbit_prio2'}  (diese Datei)
-- Fehlt der Wert: Apex → orbit_prio2, jede andere Firma → orbit_v2 (wie bisher).
--
-- (1) Spalte firmen_modell an auto_plan_gruppe (fehlt sie, liest Railway {} = Standard je Firma).
-- (2) Emins Gruppe: Lucid → orbit_prio2 (Finn). FundedNext Futures + Tradeify bei Emin erst später (nach 1–2 Tagen Beobachtung).
-- (3) Kontoart-Riegel trade_plans_kontoart_weg: der Ausnahme-Zweig für den Apex-Weg verlangte die Firma 'Apex Trader'. Damit eine andere Firma mit
--     Orbit Prio 2 umgestellt werden kann, gilt der Zweig jetzt für Apex ODER für einen Plan mit der Marke hedge_art = 'apex' (setzt nur Railway ah_tick,
--     und nur für Firmen mit Modell orbit_prio2). Alle übrigen Bedingungen bleiben Wort für Wort (challenge, tvv2, Auto-Plan, hedge_eur > 0, kein
--     Orbit V3, apex_hedge.status 'mit', Schalter prophos_apex_hedge_an()). Funktion sonst = Live-Stand vom 05.11.2026 (pg_get_functiondef).
--     OHNE (3) würde ah_tick einen Lucid-Plan zwar vormerken, das Umstellen aber am Riegel scheitern („Challenge-/Phase-Konto … nur ohne Hedge“) —
--     der Plan bliebe vom Riegel trade_plans_a1_apex_hedge gehalten und startete nie.
--
-- Rückbau: (3) die Bedingung wieder auf „public.prophos_firma_key(new.master_firm) = 'Apex Trader'“; (2) update … set firmen_modell = firmen_modell - 'lucidtrading';
--          (1) alter table public.auto_plan_gruppe drop column firmen_modell;

-- (1)
alter table public.auto_plan_gruppe add column if not exists firmen_modell jsonb not null default '{}'::jsonb;

-- (2) Gruppe „Emin“ (id_gruppen 90c616f3-3ec1-49cb-b3ba-8a267d0a43df), Lucid-Regel namen[0] = 'lucidtrading'
update public.auto_plan_gruppe
   set firmen_modell = coalesce(firmen_modell, '{}'::jsonb) || '{"lucidtrading": "orbit_prio2"}'::jsonb,
       updated_at = now()
 where gruppe_id = '90c616f3-3ec1-49cb-b3ba-8a267d0a43df';

-- (3)
CREATE OR REPLACE FUNCTION public.trade_plans_kontoart_weg()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  typ text;
  kname text;
  mit boolean;
  schalter boolean := false;
begin
  if new.master_account_id is null or coalesce(new.status, 'planned') <> 'planned' then
    return new;
  end if;
  select lower(coalesce(a.account_type, '')), a.name into typ, kname from public.accounts a where a.id = new.master_account_id;
  if typ is null then
    return new;
  end if;
  mit := public.prophos_hedge_weg(new.route, new.hedge_eur, new.orbit_v3, new.winning_day);
  if mit is null then
    return new;
  end if;
  if typ in ('funded', 'funded_cfd', 'winning_days') and not mit then
    raise exception 'Funded-Konto „%" nur mit Hedge: Weg % ohne Hedge ist für Challenges — im Trade-Popup Echo, Orbit V3, Winning Day oder Topstep (mit Hedge) wählen.',
      coalesce(kname, '?'), coalesce(new.route, '?')
      using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
  end if;
  if coalesce(new.rest_hedge, false) and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false) then
    return new;
  end if;
  -- ORBIT PRIO 2 (05.11.2026): Apex wie bisher ODER Marke hedge_art 'apex' (Railway ah_tick, nur Firmen mit Modell orbit_prio2)
  if typ = 'challenge' and coalesce(new.route, '') = 'tvv2' and coalesce(new.auto_plan, false) and coalesce(new.hedge_eur, 0) > 0
     and not coalesce(new.orbit_v3, false)
     and (public.prophos_firma_key(new.master_firm) = 'Apex Trader' or coalesce(new.mt5_baseline->>'hedge_art', '') = 'apex')
     and coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and public.prophos_apex_hedge_an() then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'mt5' and coalesce(new.auto_plan, false)
     and new.slave_account_id is not null and public.prophos_ht_echo_hedge_an() then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false)
     and coalesce(new.auto_plan, false) and coalesce(new.mt5_baseline->'tradeify_hedge'->>'status', '') = 'mit'
     and public.prophos_firma_key(new.master_firm) = public.prophos_firma_key('Tradeify')
     and public.prophos_tradeify_final_hedge_an() then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and mit and coalesce(new.route, '') in ('mt5', 'mt5v2', 'tvv2', 'tsv2') then
    select coalesce((s.value->>'an')::boolean, false) into schalter
      from public.user_settings s where s.user_id = new.user_id and s.key = 'tp_challenges_mit_hedge';
    if not coalesce(schalter, false) then
      raise exception 'Challenge-/Phase-Konto „%" nur ohne Hedge: Echo V2, Orbit V2 oder Topstep V2 wählen — oder im Trade-Popup oben „Challenges mit Hedge" einschalten.',
        coalesce(kname, '?')
        using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
    end if;
  end if;
  return new;
end $function$;

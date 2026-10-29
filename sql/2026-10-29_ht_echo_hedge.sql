-- HT ECHO-HEDGE B2 (29.10.2026, Finn: „Auf jeden Fall immer mit Echo jetzt. Es ist nicht viel für die Versicherung … Es muss nur
-- umgestellt werden zu Echo anstatt Echo V2"): HT-CFD-Challenges starten als klassisches Echo (route mt5) mit Fusion-Gegenhedge statt
-- Echo V2 (mt5v2). Umgestellt wird auf Railway (app.py eh_tick) ab 20 min vor dem Start bis zum Claim; der Planer plant weiter Echo V2.
--
-- 1. Schalter auto_plan_regeln.regeln.echo_hedge = {an, netto_faktor, min_lot, max_lots, vorlauf_min, nachlauf_min}. Standard AUS;
--    ein schon gesetzter Wert bleibt (Merge). Umschalten: Admin → Trade-Planer, Schalter „Echo-Hedge" neben „Bot an/aus", oder per SQL:
--      update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{echo_hedge,an}', 'true') where id = 1;   -- an
--      update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{echo_hedge,an}', 'false') where id = 1;  -- aus (Rückweg ohne Deploy:
--      eh_tick stellt umgestellte, noch nicht gestartete Pläne zurück auf Echo V2; laufende bleiben, wie sie sind)
-- 2. Riegel trade_plans_kontoart_weg (Hedge-Kategorien-Regel 12.10.2026): eine Challenge/Phase mit Hedge brauchte bisher den Schalter
--    der ID (user_settings tp_challenges_mit_hedge). Neu: ein AUTO-Plan auf route mt5 mit Slave darf es auch, solange regeln.echo_hedge.an
--    true ist (prophos_ht_echo_hedge_an). Alles andere unverändert (Funded nur mit Hedge, Hand-Pläne wie bisher).
-- Wiederholbar. Rückbau: Schalter aus genügt; die Funktion trade_plans_kontoart_weg ohne den Block „HT ECHO-HEDGE" neu anlegen.

update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{echo_hedge}',
         '{"an": false, "netto_faktor": 0.89, "min_lot": 0.01, "max_lots": 60, "vorlauf_min": 20, "nachlauf_min": 30}'::jsonb
         || coalesce(case when jsonb_typeof(regeln->'echo_hedge') = 'object' then regeln->'echo_hedge' end, '{}'::jsonb)),
       updated_at = now()
 where id = 1;

create or replace function public.prophos_ht_echo_hedge_an()
returns boolean language sql stable security definer set search_path to 'public' as $$
  -- nur ein echtes JSON-true zählt (kein Cast: ein Tippfehler im Schalter darf den Riegel nie mit einem Fehler abbrechen)
  select coalesce((select (r.regeln->'echo_hedge'->'an') = 'true'::jsonb from public.auto_plan_regeln r where r.id = 1), false)
$$;

create or replace function public.trade_plans_kontoart_weg()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
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
  -- Rest von Hand mit Hedge (26.10.2026): Orbit-Plan aus dem Radar-Knopf — nur tvv2 + orbit_v3, sonst gilt die Kennung nicht
  if coalesce(new.rest_hedge, false) and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false) then
    return new;
  end if;
  -- HT ECHO-HEDGE B2 (29.10.2026): Auto-Plan auf dem klassischen Echo mit Slave, solange der zentrale Schalter an ist
  if typ in ('challenge', 'phase1', 'phase2') and coalesce(new.route, '') = 'mt5' and coalesce(new.auto_plan, false)
     and new.slave_account_id is not null and public.prophos_ht_echo_hedge_an() then
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

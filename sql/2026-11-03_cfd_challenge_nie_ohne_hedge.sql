-- CFD-CHALLENGE NIE OHNE HEDGE (E1, Finn 03.11.2026 ~18:10 Dubai, wörtlich über den Master: „Alle, alle, alle CFDs, ob Phase One oder Phase Two, scheißegal
-- welche ID, der Challenge-Planer CFD: Das Modell ist immer Echo, nie Echo V2. Immer mit Hedge." und „Kümmere dich als Allererstes darum, dass nie wieder
-- überhaupt ein Echo-Trade ohne Hedge losgehen kann.").
-- Anlass: Julian (Emins Gruppe) FTMO 100k 541503873 −2.399 $ und FundingPips 100k 21165329 −1.999,60 $ am 03.11. 17:29 Dubai, beide Echo V2 ohne Fusion-Hedge;
-- dazu Emin Tradeify CFD 117332 und Amir Tradeify CFD 117533. Ursache: Handstart vor der Umstellung durch eh_tick (app.py) — der alte Riegel
-- (sql/2026-11-02_echo_ohne_hedge_riegel.sql) hielt nur Auto-Pläne MIT Marke echo_hedge {ohne, balance|lesung|groesse} und nur bei Schalter an.
-- NEU (ersetzt die Funktion trade_plans_a1_echo_hedge, Trigger und prophos_echo_fenster_ende bleiben): JEDER Start-Claim (start_claim_art 'start') eines Plans auf
-- einem Konto mit Kontoart challenge/phase1/phase2 wird gehalten, wenn
--   (a) route = 'mt5v2' (Echo V2 = ohne Hedge) — egal ob Auto- oder Hand-Plan, egal welcher Grund-Code (auch mini, klein, marge, grenze, kein_konto), egal ob Schalter an,
--   (b) route = 'mt5' (Echo) ohne Fusion-Slave (slave_account_id null) oder ohne Multiplikator > 0.
-- Konto nicht lesbar → gehalten (fail-closed). Halten wie bisher: Claim scheitert, Start rückt je 15–30 min (eh_tick kann in der Zeit umstellen),
-- start_sperre {art 'echo_hedge'}; höchstens 8 h bzw. bis CFD-Fensterende, dann aufgegeben (der Tab bucht ihn als verpasst, ⚪ aus alarm_ereignisse).
-- Verbrauchs-Claims (verpasst, Ziel erreicht) starten nichts und laufen durch. Ein Start von Hand ohne Claim wird im PC-Tab gesperrt (prophos.html echoV2Gesperrt).
-- OFFEN für Finn: Mini-Trades „Tage sammeln" (0,01 Lot, bisher bewusst ohne Hedge) werden damit ebenfalls gehalten und starten nicht mehr.
-- REIHENFOLGE: egal (der Riegel braucht keinen neuen Code), am besten vor dem Code-Push. Wiederholbar. Rückbau: sql/2026-11-02_echo_ohne_hedge_riegel.sql erneut einspielen.
-- NICHT vom Slave eingespielt.

create or replace function public.trade_plans_a1_echo_hedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  eh jsonb;
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
  erst_at timestamptz;
  grund text;
  kt text;
  gefunden boolean;
begin
  if new.status is distinct from 'planned' or coalesce(new.start_claim_art, 'start') <> 'start'
     or coalesce(new.route, '') not in ('mt5v2', 'mt5') then
    return new;
  end if;
  select lower(coalesce(a.account_type, '')), true into kt, gefunden from public.accounts a where a.id = new.master_account_id;
  if coalesce(gefunden, false) and kt <> '' and kt not in ('challenge', 'phase1', 'phase2') then   -- leere Kontoart = nicht lesbar (Prüfung 03.11.2026)
    return new;                                   -- Funded CFD u. a.: eigene Regeln (trade_plans_kontoart_weg)
  end if;
  if new.route = 'mt5' and new.slave_account_id is not null and coalesce(new.multiplier, 0) > 0 then
    return new;                                   -- Echo mit Fusion-Slave: gehedgt
  end if;
  eh := new.mt5_baseline->'echo_hedge';
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'echo_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  if ss->>'art' = 'echo_hedge' and ss->>'status' = 'aufgegeben' then
    return null;                                  -- aufgegeben bleibt aufgegeben (Stopp S17 02.11.2026)
  end if;
  erst := coalesce(ss->>'art', '') <> 'echo_hedge';
  erst_at := case when erst then now() else coalesce((ss->>'erst_at')::timestamptz, now()) end;
  txt := case
    when not coalesce(gefunden, false) or kt = '' then 'Kontoart des Masters nicht lesbar — CFD-Challenge vermutet, nie ohne Hedge'
    when new.route = 'mt5' then 'Echo ohne Fusion-Slave/Multiplikator — CFD-Challenges nur mit Hedge'
    when eh->>'status' = 'ohne' then 'Echo-Hedge nicht umgestellt: ' || left(coalesce(eh->>'grund', eh->>'code', '?'), 160)
    else 'Echo V2 (ohne Hedge) — CFD-Challenges laufen immer mit Fusion-Hedge, Umstellung steht noch aus' end;
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  grund := case when erst_at < now() - interval '8 hours' then '8h'
                when ziel >= public.prophos_echo_fenster_ende(erst_at) then 'fenster' end;
  if grund is not null then
    if erst or coalesce(ss->>'status', '') <> 'aufgegeben' then
      update public.trade_plans
         set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
               'art', 'echo_hedge', 'status', 'aufgegeben', 'ablauf', grund, 'text', txt, 'at', now(), 'erst_at', erst_at,
               'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
       where id = new.id;
      insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
      values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, old.start_um,
              '[Echo ohne Hedge aufgegeben] ' || txt || case when grund = 'fenster' then ' — CFD-Startfenster zu Ende' else ' — nach 8 h' end, 'start');
    end if;
    return null;
  end if;
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'echo_hedge', 'text', txt, 'at', now(), 'naechster', ziel, 'erst_at', erst_at,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Echo ohne Hedge gehalten] ' || txt || ' — Start rückt je 15–30 min weiter, bis der Hedge steht, höchstens 8 h', 'start');
  end if;
  return null;
end $$;

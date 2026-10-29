-- EINGESPIELT 29.10.2026 ~23:35 Dubai (Master, nach S2-OK)
-- APEX IMMER MIT HEDGE — NACHTRAG HAND-WERTE (30.10.2026, Prüfer S2 / Master, Variante 2: „Finns Regel heißt Apex immer mit Hedge, auch nach
-- Hand-Werten wird nicht ohne Hedge gestartet"). Ein markierter Apex-Plan (hedge_art 'apex') mit späteren Hand-Werten (hand_werte_at) wird
-- von ah_tick nie mehr umgestellt; der Claim-Riegel trade_plans_a1_apex_hedge hält ihn weiter, der Sperrtext (start_sperre.text, ⚪ einmal,
-- Radar) sagt jetzt: „Apex wartet auf Hedge — Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen".
-- Nur die Funktion (Trigger bleibt); wortgleich mit sql/2026-10-30_apex_immer_hedge.sql. Voraussetzung: diese Datei ist eingespielt (live).
-- Wiederholbar. Rückbau: Funktion aus dem Stand vor diesem Nachtrag (git f101aeaf, sql/2026-10-30_apex_immer_hedge.sql) neu anlegen.

do $pruef$
begin
  perform 'public.trade_plans_a1_apex_hedge()'::regprocedure;
exception when undefined_function then
  raise exception 'Erst sql/2026-10-30_apex_immer_hedge.sql einspielen';
end $pruef$;

create or replace function public.trade_plans_a1_apex_hedge()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  ss jsonb;
  ziel timestamptz;
  erst boolean;
  txt text;
begin
  if new.status is distinct from 'planned' or not coalesce(new.auto_plan, false)
     or coalesce(new.mt5_baseline->>'hedge_art', '') <> 'apex' then
    return new;
  end if;
  -- umgestellt (ah_tick: WD-Weg mit Fusion-Gegenhedge) → darf starten
  if coalesce(new.mt5_baseline->'apex_hedge'->>'status', '') = 'mit' and coalesce(new.hedge_eur, 0) > 0 then
    return new;
  end if;
  if not public.prophos_apex_hedge_an() then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  if ss->>'art' = 'apex_hedge' and (ss->>'at')::timestamptz > now() - interval '1 minute' then
    return null;                                  -- Mehrfach-Claim: schon eben gehalten, nicht neu schieben
  end if;
  erst := coalesce(ss->>'art', '') <> 'apex_hedge';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  -- Hand-Werte (Master 30.10.2026, Variante 2): ah_tick stellt solche Pläne nie mehr um — weiter halten (nie ohne Hedge), Grund sagt es
  if new.hand_werte_at is not null then
    txt := 'Apex wartet auf Hedge — Werte von Hand geändert, Takt stellt nicht mehr um: ablehnen und neu planen';
  else
    txt := 'Apex-Challenge wartet auf Gegenhedge'
           || coalesce(' (' || nullif(left(new.mt5_baseline->'apex_hedge'->>'grund', 160), '') || ')', ' (noch nicht umgestellt)');
  end if;
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'apex_hedge', 'text', txt, 'at', now(), 'naechster', ziel,
           'erst_at', case when erst then now() else coalesce(ss->'erst_at', to_jsonb(now())) end,
           'versuche', case when erst then 1 else coalesce((ss->>'versuche')::int, 0) + 1 end))
   where id = new.id;
  if erst then
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Apex ohne Hedge gehalten] ' || txt || ' — startet nie ohne Hedge; Start rückt je 15–30 min weiter, bis der Hedge rechenbar ist',
            'start');
  end if;
  return null;
end $$;

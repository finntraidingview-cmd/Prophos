-- 2026-09-25 · Atomare Sperre in trade_plans.mt5_baseline (ein Tab je Plan-Aktion)
--
-- Anlass (Gegenprüfung der Koordination zu .578): seit .571 teilen sich alle Chrome-Profile eines PCs dieselbe PC-Kennung — zwei
-- Tabs bewachen denselben Fusion-Hedge. Schließen, Plan-auf-Überprüfen und Selbstheilung dürfen nur EINMAL laufen. Lesen-dann-Setzen
-- im Browser lässt ein Fenster von 100–300 ms, in dem beide Tabs „frei" sehen; der zweite überschreibt dann grund/ausloeser.
-- Diese Funktion setzt mt5_baseline[p_key] = {tab, at} in EINEM Statement (Zeilensperre des UPDATE) — nur wenn der Schlüssel leer ist,
-- schon diesem Tab gehört oder älter als p_sek Sekunden ist. Rückgabe true = dieser Tab hält die Sperre, false = ein anderer Tab.
-- security invoker: es gilt die RLS des Nutzers („users can update own trade_plans").

create or replace function public.mt5_baseline_sperre(p_plan uuid, p_key text, p_tab text, p_sek integer default 20)
returns boolean
language sql
security invoker
set search_path = public
as $$
  with u as (
    update public.trade_plans
       set mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), array[p_key],
                                    jsonb_build_object('tab', p_tab, 'at', to_jsonb(now())), true)
     where id = p_plan
       and coalesce(p_key, '') <> '' and coalesce(p_tab, '') <> ''
       and (    mt5_baseline -> p_key is null
             or jsonb_typeof(mt5_baseline -> p_key) <> 'object'
             or mt5_baseline -> p_key ->> 'tab' = p_tab
             or coalesce(mt5_baseline -> p_key ->> 'at', '') = ''
             or (mt5_baseline -> p_key ->> 'at')::timestamptz < now() - make_interval(secs => greatest(coalesce(p_sek, 20), 1)) )
    returning 1
  )
  select exists (select 1 from u);
$$;

revoke all on function public.mt5_baseline_sperre(uuid, text, text, integer) from public, anon;
grant execute on function public.mt5_baseline_sperre(uuid, text, text, integer) to authenticated, service_role;

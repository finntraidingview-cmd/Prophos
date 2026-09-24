-- 2026-09-25 · mt5_baseline atomar mergen statt Lesen-Ändern-Schreiben im Browser
--
-- Anlass (zweite Gegenprüfung der Hedge-Kette, Stand .549): mehrere Schreiber von trade_plans.mt5_baseline
-- (Rundgang live/final/fehler, tvV2EndeSetzen, v2PlanAufOpen, einstieg_nq, hedgeAmPlanSchreiben) bauen das ganze
-- jsonb aus einem ALTEN Plan-Objekt im Tab neu auf und schreiben es zurück. Dazwischen schreibt der Hedge-Wächter
-- alle 10 s in mt5_baseline.hedge → der Rundgang setzte einen schon geschlossenen Hedge auf 'offen' zurück bzw.
-- löschte einen frisch angelegten. Diese Funktionen mergen IN DER DATENBANK, in einem Statement (Zeilensperre des
-- UPDATE) — kein Schreiber kann die Felder eines anderen mehr überschreiben.
--
-- mt5_baseline_patch(plan, patch [, status])       : oberste Ebene, mt5_baseline || patch
--                                                    (z. B. {"live": {...}} oder {"final": {...}} — ersetzt NUR diese Schlüssel)
-- mt5_baseline_patch_in(plan, key, patch [, status]): eine Ebene tiefer, mt5_baseline[key] || patch
--                                                    (z. B. key 'hedge', patch {"status":"geschlossen","pl":-4.2} — der Rest von hedge bleibt)
-- p_status (optional): nur schreiben, wenn trade_plans.status = p_status (Ersatz für .eq('status','open')).
-- Rückgabe: das neue mt5_baseline — NULL, wenn keine Zeile geschrieben wurde (Plan fehlt, fremder Plan unter RLS,
-- Status-Guard griff). security invoker: es gilt die RLS des aufrufenden Nutzers („users can update own trade_plans").

create or replace function public.mt5_baseline_patch(p_plan uuid, p_patch jsonb, p_status text default null)
returns jsonb
language sql
security invoker
set search_path = public
as $$
  update public.trade_plans
     set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || coalesce(p_patch, '{}'::jsonb)
   where id = p_plan
     and (p_status is null or status = p_status)
  returning mt5_baseline;
$$;

create or replace function public.mt5_baseline_patch_in(p_plan uuid, p_key text, p_patch jsonb, p_status text default null)
returns jsonb
language sql
security invoker
set search_path = public
as $$
  update public.trade_plans
     set mt5_baseline = jsonb_set(
           coalesce(mt5_baseline, '{}'::jsonb),
           array[p_key],
           (case when jsonb_typeof(mt5_baseline -> p_key) = 'object' then mt5_baseline -> p_key else '{}'::jsonb end)
             || coalesce(p_patch, '{}'::jsonb),
           true)
   where id = p_plan
     and (p_status is null or status = p_status)
     and coalesce(p_key, '') <> ''
  returning mt5_baseline;
$$;

revoke all on function public.mt5_baseline_patch(uuid, jsonb, text) from public, anon;
revoke all on function public.mt5_baseline_patch_in(uuid, text, jsonb, text) from public, anon;
grant execute on function public.mt5_baseline_patch(uuid, jsonb, text) to authenticated, service_role;
grant execute on function public.mt5_baseline_patch_in(uuid, text, jsonb, text) to authenticated, service_role;

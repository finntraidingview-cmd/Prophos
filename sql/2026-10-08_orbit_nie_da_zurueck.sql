-- ORBIT V3 „MASTER NIE GEFÜLLT" → START-FEHLER + NEU EINPLANEN (08.10.2026, Finn über Master: Hedge-Schluss mit grund master_nie_da
-- „als START-FEHLER behandeln und NEU EINPLANEN wie andere Startfehler"). Der PC-Tab (Hedge-Wächter, prophos.html hedgeNieDaPruefen) ruft
-- diese Funktion erst, wenn der Puls-Chrome-Reader das Plan-Konto ≥ 60 s mit ≥ 6 Lesungen flach zeigt und Puls keinen Fill gemeldet hat.
--
-- Setzt den Plan ATOMAR zurück auf „geplant" (Claim bleibt — sfTick plant von dort wie jeden Start-Fehler neu ein, der neue Claim läuft
-- wieder durch Firmen-Abstand und Gegenhedge-Riegel): status planned, started_at/orbit_gesendet_at null, mt5_baseline ohne tv/hedge/live/
-- final, der alte Versuch bleibt unter versuche_alt[] stehen (Hedge-Ticket, P&L, Puls-Werte), start_fehler = p_flag.
-- Guard: nur ein offener tvv2-Plan ohne Ende, dessen Hedge wegen master_nie_da geschlossen ist, ohne final und ohne puls_unklar — sonst
-- 0 Zeilen. Der Tab ruft erst, wenn kein order_signale des Plans mehr läuft und die puls_ergebnisse-Zeile da ist (spätes Ergebnis), und
-- pulsErgebnisseUebernehmen verwirft Klicks vor versuche_alt[-1].zurueck_at.
-- SECURITY INVOKER: RLS gilt (der Tab ändert nur eigene Pläne). Trigger auf trade_plans feuern nur beim Claim (start_um_gestartet_at
-- null → gesetzt), nicht hier. Rückbau: drop function if exists public.prophos_orbit_nie_da_zurueck(uuid, jsonb);

create or replace function public.prophos_orbit_nie_da_zurueck(p_plan uuid, p_flag jsonb)
returns setof public.trade_plans
language sql
security invoker
set search_path to 'public'
as $$
  update public.trade_plans t
     set status = 'planned',
         started_at = null,
         orbit_gesendet_at = null,
         mt5_baseline = (coalesce(t.mt5_baseline, '{}'::jsonb) - 'tv' - 'hedge' - 'live' - 'final')
           || jsonb_build_object(
                'start_fehler', coalesce(p_flag, '{}'::jsonb),
                'versuche_alt', coalesce(t.mt5_baseline -> 'versuche_alt', '[]'::jsonb)
                  || jsonb_build_array(jsonb_build_object('zurueck_at', now(), 'started_at', t.started_at,
                       'tv', t.mt5_baseline -> 'tv', 'hedge', t.mt5_baseline -> 'hedge')))
   where t.id = p_plan
     and t.status = 'open'
     and t.route = 'tvv2'
     and t.ended_at is null
     and t.mt5_baseline -> 'hedge' ->> 'status' = 'geschlossen'
     and t.mt5_baseline -> 'hedge' ->> 'grund' = 'master_nie_da'
     and t.mt5_baseline -> 'final' is null
     and coalesce(jsonb_typeof(t.mt5_baseline -> 'puls_unklar'), 'null') = 'null'   -- Puls UNKLAR: nie neu einplanen (Order kann noch hängen) — Slave-2-Prüfung; ein gelöschtes {puls_unklar: null} zählt nicht
  returning t.*;
$$;

revoke all on function public.prophos_orbit_nie_da_zurueck(uuid, jsonb) from public, anon;
grant execute on function public.prophos_orbit_nie_da_zurueck(uuid, jsonb) to authenticated, service_role;

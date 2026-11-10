-- ÜBERHOLT 11.11.2026 (FS2 K3): NICHT einspielen — ersetzt durch sql/2026-11-11_fs2_k3_wartet.sql (gleiche Views, mehr Warte-Gründe).
-- 2026-11-10 — FS1 Zählung (Master nach FS1; Finn: „Ich will die Ursache fixen, damit ich nicht jeden Tag wieder zehn Fehlstarts habe.“)
-- Big-Trade-Warten ist kein Fehlstart: Puls bleibt im Konto, weil der Big Trade dieses PCs nah an TP/Liq steht (Regel puls_heim_regel), nichts gesendet,
-- der Plan startet später (FS1: 19 von 21 Plänen in 7 Handelstagen, im Schnitt 68 min später). Bisher zählten diese Zeilen in puls_fehler_muster
-- (n_7d, Routine „Puls-Fehler“, fehler-analyse.md) wie echte Fehler.
-- Neu: puls_fehler_ereignisse bekommt hinten die Spalte art ('wartet' | 'fehler'); puls_fehler_muster zählt nur art = 'fehler'; die Warte-Zeilen stehen in der
-- neuen View puls_wartet_muster (gleiche Spalten). Nichts wird gelöscht, puls_fehlstarts bleibt unverändert. Spalten der bestehenden Views bleiben gleich
-- (art kommt nur hinten dazu), security_invoker wie bisher.
-- Hinweis: fehlstart_doktor liest puls_fehlstarts direkt und zählt Big-Trade-Warten weiter (dort ohne Rezept = „nichts“).
-- Vor dem Einspielen gegen pg_get_viewdef des Live-Stands abgleichen (Stand 10.11.2026 20:40 Dubai geprüft, Probelauf mit Rollback: 580 Fehler + 23 Warten = 603).
-- Rückbau: die beiden Views mit der Definition aus pg_get_viewdef vor diesem Stand neu anlegen (ohne art / ohne where), puls_wartet_muster droppen.
create or replace view public.puls_fehler_ereignisse with (security_invoker = true) as
 select f.at, f.user_id, f.plan_id, f.route, f.pc, f.schritt, f.msg, f.unklar, 'start_um'::text as quelle, f.bild_pfad,
        case when f.schritt in ('big_trade_nah', 'big_trade_unklar') then 'wartet' else 'fehler' end as art
   from public.puls_fehlstarts f
union all
 select s.created_at as at, s.user_id, s.plan_id, null::text as route, s.pc,
        coalesce(s.ergebnis ->> 'schritt', s.ergebnis ->> 'code', s.params ->> 'aktion', 'signal') as schritt,
        s.ergebnis ->> 'msg' as msg,
        coalesce((s.ergebnis ->> 'unklar')::boolean, false) as unklar,
        'signal'::text as quelle,
        case when (s.ergebnis ->> 'fehlerbild') ~ '^pc-[a-z0-9]{4,12}/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$'
             then s.ergebnis ->> 'fehlerbild' else null::text end as bild_pfad,
        case when coalesce(s.ergebnis ->> 'schritt', s.ergebnis ->> 'code', s.params ->> 'aktion', 'signal') in ('big_trade_nah', 'big_trade_unklar')
             then 'wartet' else 'fehler' end as art
   from public.order_signale s
  where s.status = 'fehler';

create or replace view public.puls_fehler_muster with (security_invoker = true) as
 select public.puls_fehler_muster_text(schritt, msg) as muster,
        count(*) filter (where at > now() - interval '24 hours') as n_24h,
        count(*) filter (where at > now() - interval '7 days') as n_7d,
        count(*) filter (where at > now() - interval '30 days') as n_30d,
        count(*) filter (where unklar) as n_unklar,
        array_agg(distinct pc) filter (where pc is not null) as pcs,
        count(distinct user_id) as ids,
        max(at) as zuletzt,
        (array_agg(msg order by at desc))[1] as beispiel,
        (array_agg(bild_pfad order by at desc) filter (where bild_pfad is not null))[1] as bild
   from public.puls_fehler_ereignisse e
  where e.art = 'fehler'
  group by public.puls_fehler_muster_text(schritt, msg);

create or replace view public.puls_wartet_muster with (security_invoker = true) as
 select public.puls_fehler_muster_text(schritt, msg) as muster,
        count(*) filter (where at > now() - interval '24 hours') as n_24h,
        count(*) filter (where at > now() - interval '7 days') as n_7d,
        count(*) filter (where at > now() - interval '30 days') as n_30d,
        count(*) filter (where unklar) as n_unklar,
        array_agg(distinct pc) filter (where pc is not null) as pcs,
        count(distinct user_id) as ids,
        max(at) as zuletzt,
        (array_agg(msg order by at desc))[1] as beispiel,
        (array_agg(bild_pfad order by at desc) filter (where bild_pfad is not null))[1] as bild
   from public.puls_fehler_ereignisse e
  where e.art = 'wartet'
  group by public.puls_fehler_muster_text(schritt, msg);

-- wie die beiden bestehenden Views: nur lesen für die Rollen der App
revoke all on public.puls_wartet_muster from anon;
grant select on public.puls_wartet_muster to authenticated, service_role;

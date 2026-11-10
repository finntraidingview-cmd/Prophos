-- 2026-11-11 — FS2 K3: gewolltes Warten zählt nicht als Fehlstart (Master 11.11.2026 nach dem FS2-Befund, Finn „Ja“ zu den Fehlstart-Fixes;
-- Finn 11.11.: „Es kommen immer noch sehr oft Fehlstarts aus irgendeinem Grund, und das nervt“).
-- ERSETZT sql/2026-11-10_fs1_wartet_zaehlung.sql (FS1, nie eingespielt) — dieselben drei Views, die Einordnung jetzt in EINER Funktion
-- puls_fehler_art(schritt, msg) und um alle gewollten Warte-Gründe erweitert. Nur diese Datei einspielen, die FS1-Datei NICHT.
--
-- 'wartet' (nichts gesendet, der Plan startet später von selbst bzw. bewusst nicht; Quelle: Code auf origin/main 11.11.2026):
--   big_trade_nah / big_trade_unklar  Puls bleibt im Konto, Big Trade bzw. Winning-Day-/Apex-Riegel nah an TP/Liq (app.py PULS_HEIM_CODE_NAH/UNKLAR;
--                                     der WD-/Apex-Riegel nutzt denselben Code, Text beginnt mit „Winning Day“ bzw. „Apex-Challenge“)
--   zweit_wartet / firma_laeuft / markt_oeffnung  Zwei-Orbit-Regel, je Firma einer, Markteröffnung 09:28–09:35 NY (app.py PULS_HEIM_CODE_ZWEIT/FIRMA/MARKT)
--   ziel_erreicht                     Konto hat sein Ziel — bewusst kein Start
--   manuelle_arbeit                   Konto steht auf „Manuelle Arbeit“ — bewusst kein Start
--   Text „zweiter Start wartet“; Anfang „Winning Day …“/„Apex-Challenge …“ (auch mit „⛔ “ davor) NUR bei schritt big_trade_* oder ohne schritt
--                                     (Prüfer-Stopp 610ae82c: sonst fielen echte Fehler wie „Winning Day nicht gezählt — …“ darunter)
-- Bewusst 'fehler' bleiben: index_pause (Prüfer-Stopp 610ae82c: sfMelden schreibt es nur im Aufgeben-Zweig — „Startfenster zu Ende, nicht gestartet“,
-- der Plan ist verbraucht, das Frontend behandelt es wie riegel_aufgegeben), riegel_aufgegeben (der Trade fiel aus, Finn muss ran), zu_spaet, unklar
-- und alles andere.
--
-- Wirkung: puls_fehler_muster (Routine „Puls-Fehler“, fehler-analyse.md) zählt nur art = 'fehler'; die Warte-Zeilen stehen in puls_wartet_muster (gleiche
-- Spalten). Nichts wird gelöscht, puls_fehlstarts/order_signale bleiben unverändert; puls_fehler_ereignisse bekommt hinten die Spalte art.
-- fehlstart_doktor liest puls_fehlstarts direkt — dort ändert sich nichts (Warten hat kein Rezept = „nichts“).
-- VOR DEM EINSPIELEN: pg_get_viewdef('public.puls_fehler_ereignisse') und ('public.puls_fehler_muster') mit dem Stand unten abgleichen (Spalten und
-- Reihenfolge wie 2026-10-29_puls_fehlerbilder*.sql); weicht der Live-Stand ab, die Abweichung hier übernehmen, nicht überschreiben.
-- Rückbau: beide Views mit der Definition aus pg_get_viewdef vor diesem Stand neu anlegen (ohne art / ohne where), puls_wartet_muster und
-- puls_fehler_art droppen.

create or replace function public.puls_fehler_art(schritt text, msg text)
returns text language sql immutable as $$
  select case
    when coalesce(schritt, '') in ('big_trade_nah', 'big_trade_unklar', 'zweit_wartet', 'firma_laeuft', 'markt_oeffnung',
                                   'ziel_erreicht', 'manuelle_arbeit') then 'wartet'
    when coalesce(msg, '') ~* 'zweiter Start wartet' then 'wartet'
    when coalesce(schritt, '') in ('', 'big_trade_nah', 'big_trade_unklar')
         and coalesce(msg, '') ~ '^\W*(Winning Day|Apex-Challenge)\M' then 'wartet'
    else 'fehler' end
$$;

create or replace view public.puls_fehler_ereignisse with (security_invoker = true) as
 select f.at, f.user_id, f.plan_id, f.route, f.pc, f.schritt, f.msg, f.unklar, 'start_um'::text as quelle, f.bild_pfad,
        case when f.unklar then 'fehler' else public.puls_fehler_art(f.schritt, f.msg) end as art
   from public.puls_fehlstarts f
union all
 select s.created_at as at, s.user_id, s.plan_id, null::text as route, s.pc,
        coalesce(s.ergebnis ->> 'schritt', s.ergebnis ->> 'code', s.params ->> 'aktion', 'signal') as schritt,
        s.ergebnis ->> 'msg' as msg,
        coalesce((s.ergebnis ->> 'unklar')::boolean, false) as unklar,
        'signal'::text as quelle,
        case when (s.ergebnis ->> 'fehlerbild') ~ '^pc-[a-z0-9]{4,12}/[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$'
             then s.ergebnis ->> 'fehlerbild' else null::text end as bild_pfad,
        case when coalesce((s.ergebnis ->> 'unklar')::boolean, false) then 'fehler'
             else public.puls_fehler_art(coalesce(s.ergebnis ->> 'schritt', s.ergebnis ->> 'code', s.params ->> 'aktion', 'signal'),
                                         s.ergebnis ->> 'msg') end as art
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

-- wie die bestehenden Views: nur lesen für die Rollen der App
revoke all on public.puls_wartet_muster from anon;
grant select on public.puls_wartet_muster to authenticated, service_role;
grant execute on function public.puls_fehler_art(text, text) to authenticated, service_role;

-- Probe nach dem Einspielen (nur lesen): Verteilung der letzten 7 Tage, nur HT
-- select e.art, count(*) from puls_fehler_ereignisse e
--   join id_gruppen_uebersicht g on g.user_id = e.user_id and g.gruppe = 'Hermann Technologies'
--  where e.at > now() - interval '7 days' group by e.art;

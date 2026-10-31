-- 31.10.2026 (S7, Auftrag J1): Echo mit Fusion-Hedge (route mt5) zieht den SL bei Plan + 15 % jetzt ebenfalls am Fill nach
-- (order_bot.nachzieh_cmd). Die Statistik soll beide Echo-Wege sehen: gegenüber sql/2026-10-26_justage_view.sql ändert sich nur der
-- Filter route = 'mt5v2' → route in ('mt5v2', 'mt5'). Idempotent (create or replace). Der Regex-Filter bleibt, darum zählen nur Trades mit Auslöser.
-- Einspielen erst, wenn der Bot-Stand live ist; ohne dieses SQL läuft alles, nur die View zeigt Echo mit Hedge nicht.
-- JUSTAGE — Statistik zum Nachziehen von TP/SL am echten Fill (26.10.2026, Finn: das System „TP/SL nach dem Fill am echten Entry nachziehen
-- + robuster Ändern-Klick" heißt ab jetzt „Justage"; er will sehen, wann genau sie gegriffen hat und ob es funktioniert hat).
--
-- Nur Views, nur lesend, wiederholbar (create or replace), security_invoker wie puls_fehler_ereignisse — es gelten die RLS-Rechte des Lesers.
-- Anleitung + Bewertungsregel: .claude/justage.md. Rückbau am Ende der Datei.
--
-- WO DIE DATEN LIEGEN (geprüft 26.10.2026 per SELECT, kein eigenes Feld in der DB — alles steht als Text in der Spur):
--   Echo V2 (mt5v2)  trade_plans.mt5_baseline.puls_spur {at, ok, pc, msg, trail}. Das Objekt nachzug aus order_bot._sltp_nachziehen
--                    kommt NICHT in der DB an (puls_spur trägt nur at/ok/pc/msg/trail/zeiten/s). Ergebnis daher aus msg
--                    („…, am Fill nachgezogen" bzw. „— Nachziehen: <Grund>"), Zeiten/Werte aus trail („14.8s·Final: pass (…) → nur TP am
--                    Fill nachziehen → 14.8s·Nachziehen am Fill <Fill>: SL a / TP b statt c / d (x $ daneben, …) → … Aendern-Dialog offen …
--                    → 26.2s·SL a / TP b am Fill nachgezogen (TP, Versuch 1)"). trail wird hinten gekürzt — dann fehlt nur dauer_s.
--   Orbit (tvv2)     SEIT .1749 OHNE JUSTAGE (Revert) — der Zweig bleibt für die Fälle 26.10. und liefert sonst nichts.
--                    order_signale (params.aktion = 'orbit').ergebnis.trail, Zeile „<t>s·Nachziehen am Fill: <teile, durch ' · '>"
--                    (order_bot._cdp_nachziehen, nur mit '@final=pass' / '@tages_grenze_usd='; die Marken selbst stehen nicht in der DB,
--                    der Auslöser kommt aus den Teilen: „TP … > Ziel" = ziel, „SL … > Grenze" = tagesgrenze). pruefung.nachziehen landet
--                    nur in puls_ergebnisse (eine Zeile je Plan, wird überschrieben) — deshalb hier die Spur.
--   Polar            polar_lauf.slave.level {ok, sl, tp, quelle airbag|plan|notfall, notfall{sl,tp}, grund} + slave.schritte[] (phase
--                    gefuellt/level mit at_ms). Polar setzt immer beide Seiten ab dem eigenen Fill (Airbag), Auslöser = quelle.
--
-- Spalten justage_ereignisse (eine Zeile je Justage-Fall):
--   at (Dubai, ohne Zone) · at_utc · tag (Dubai-Datum) · wer (Name der ID) · gruppe · user_id · plan_id · route echo|orbit|polar ·
--   ausloeser ziel|blow|tagesgrenze|plan (plan = Echo-SL ab Fill > Plan + 15 %, ab .1751; kombiniert mit '+'), Polar airbag|plan|notfall · seite tp|sl|beide ·
--   ergebnis nachgezogen|abgebrochen|nicht_noetig|unklar · grund · dauer_s (Beginn der Justage → bestätigt/abgebrochen;
--   dauer_ca = true: Spur gekürzt, gerechnet bis Lauf-Ende) ·
--   abweichung_vorher_usd / abweichung_nachher_usd (so weit lagen die groben Level daneben, davor/danach) · levels_vorher/levels_nachher ·
--   aendern_dialoge (wie oft der Ändern-Dialog aufging) · aendern_punkte (höchster Scan-Punkt „Punkt n", Echo ab .1746) · versuche ·
--   frist_erreicht (Ändern-Frist 20 s Echo / 25 s Orbit) · pc · quelle_id (Plan-, Signal- bzw. Lauf-ID).

create or replace view public.justage_ereignisse with (security_invoker = true) as
with
echo as (
  select p.id as plan_id, p.user_id, p.mt5_baseline->'puls_spur' as ps,
         coalesce(p.mt5_baseline->'puls_spur'->>'trail', '') as tr, coalesce(p.mt5_baseline->'puls_spur'->>'msg', '') as msg,
         coalesce(nullif(p.mt5_baseline->'puls_spur'->>'at', '')::timestamptz, p.started_at) as at_utc
  from public.trade_plans p
  where p.route in ('mt5v2', 'mt5')   -- Echo mit Hedge seit 31.10.2026 (nur SL bei Plan + 15 %): dieselbe Spur
    -- ab .1751 (S1 f4e938d2): SL-Auslöser „SL: Verlust bis SL X $ > Plan Y $ + 15 % → am Fill“ / „… > Tagesgrenze Z $ → am Fill“, auch bei
    -- Final keins — jeder Klick-Fall hat „→ nur TP|SL|TP+SL am Fill nachziehen“; die Muster bis .1750 bleiben mitgelesen
    and p.mt5_baseline->'puls_spur'->>'trail' ~ 'Final: (pass|blow|beide)|Tagesgrenze: Verlust bis SL [^→]* > |SL: Verlust bis SL [^→]* > (Plan|Tagesgrenze) |nur (TP\+SL|TP|SL) am Fill nachziehen'
),
echo_z as (
  select e.*,
         case when e.msg ~ 'am Fill nachgezogen' or e.tr ~ 'am Fill nachgezogen \(' then 'nachgezogen'
              when e.tr ~ 'Nachziehen unnötig' then 'nicht_noetig'
              when e.msg ~ 'Nachziehen: ' or e.tr ~ '·Nachziehen: ' or e.ps->>'ok' = 'false' then 'abgebrochen'
              else 'unklar' end as ergebnis,
         regexp_match(e.tr, 'Nachziehen am Fill [0-9.]+: SL ([0-9.]+) / TP ([0-9.]+) statt ([0-9.]+) / ([0-9.]+) \(([0-9.]+) \$ daneben') as lv,
         substring(e.tr from '([0-9]+\.[0-9]+)s·(Tagesgrenze: Verlust|SL: Verlust bis SL [^→]* > (Plan|Tagesgrenze) |Final: )')::numeric as t0,
         coalesce(substring(e.tr from '([0-9]+\.[0-9]+)s·SL [^→]* am Fill nachgezogen'),
                  substring(e.tr from '([0-9]+\.[0-9]+)s·Nachziehen: '),
                  substring(e.tr from '([0-9]+\.[0-9]+)s·Nachziehen unnötig'))::numeric as t1
  from echo e
),
echo_f as (
  select z.at_utc, z.user_id, z.plan_id::text as plan_id, 'echo'::text as route,
         nullif(concat_ws('+',
           case when z.tr ~ 'Final: beide' then 'ziel+blow' when z.tr ~ 'Final: pass' then 'ziel' when z.tr ~ 'Final: blow' then 'blow' end,
           case when z.tr ~ 'Tagesgrenze: Verlust bis SL [^→]* > |SL: Verlust bis SL [^→]* > Tagesgrenze |\(SL wegen Tagesgrenze\)' then 'tagesgrenze'
                when z.tr ~ 'SL: Verlust bis SL [^→]* > Plan |\(SL wegen Plan \+ 15 %\)' then 'plan' end), '') as ausloeser,
         case substring(z.tr from 'nur (TP\+SL|TP|SL) am Fill nachziehen') when 'TP' then 'tp' when 'SL' then 'sl' when 'TP+SL' then 'beide' end as seite,
         z.ergebnis,
         case z.ergebnis
           when 'nachgezogen' then coalesce('Versuch ' || substring(z.tr from 'am Fill nachgezogen \([^,]*, Versuch ([0-9]+)\)'), 'bestätigt')
           when 'nicht_noetig' then substring(z.tr from 'Nachziehen unnötig: ([^→]*)')
           when 'abgebrochen' then coalesce(substring(z.msg from 'Nachziehen: (.*?)( · [0-9]+s)?$'), substring(z.tr from '·Nachziehen: ([^→]*)'),
                                            left(z.msg, 200))
           else substring(z.tr from 'Final: [a-z]+ \(([^)]*)\)') end as grund,
         -- Spur hinten gekürzt (Ende fehlt): Gesamtzeit aus msg „… · 101s“ minus Beginn — reicht bis zum Lauf-Ende, daher dauer_ca
         round(coalesce(z.t1, case when z.ergebnis in ('nachgezogen', 'abgebrochen') then substring(z.msg from '· ([0-9]+)s$')::numeric end) - z.t0, 1) as dauer_s,
         z.t1 is null and z.ergebnis in ('nachgezogen', 'abgebrochen') and z.msg ~ '· [0-9]+s$' as dauer_ca,
         (z.lv)[5]::numeric as abweichung_vorher_usd,
         case z.ergebnis when 'nachgezogen' then 0 when 'unklar' then null else (z.lv)[5]::numeric end as abweichung_nachher_usd,
         case when z.lv is not null then 'SL ' || (z.lv)[3] || ' / TP ' || (z.lv)[4] end as levels_vorher,
         case when z.lv is not null then 'SL ' || (z.lv)[1] || ' / TP ' || (z.lv)[2] end as levels_nachher,
         (select count(*) from regexp_matches(z.tr, 'Aendern-Dialog offen', 'g'))::int as aendern_dialoge,
         (select max(m[1]::int) from regexp_matches(z.tr, 'Punkt ([0-9]+)', 'g') m) as aendern_punkte,
         coalesce((select max(m[1]::int) from regexp_matches(z.tr, 'Nachziehen Versuch ([0-9]+)/', 'g') m),
                  case when z.tr ~ 'Aendern-Dialog offen|Handel-Tab' then 1 end) as versuche,
         z.tr ~ 'Frist [0-9.]+ s erreicht' as frist_erreicht,
         z.ps->>'pc' as pc, z.plan_id::text as quelle_id
  from echo_z z
),
orbit as (
  select s.id, s.plan_id, s.user_id, s.pc, coalesce(s.updated_at, s.created_at) as at_utc,
         coalesce(s.ergebnis->>'trail', '') as tr,
         substring(s.ergebnis->>'trail' from '·Nachziehen am Fill: (.*?)( > [0-9]+\.[0-9]+s·|$)') as nz
  from public.order_signale s
  where s.params->>'aktion' = 'orbit' and s.ergebnis->>'trail' ~ '·Nachziehen am Fill: '
),
orbit_z as (
  select o.*,
         case when o.nz ~ '^(kein Fill|kein Punktwert|Soll nicht rechenbar)' then null
              else nullif(concat_ws('+', case when o.nz ~ 'TP [0-9.]+ brächte' then 'tp' end, case when o.nz ~ 'SL [0-9.]+ kostete' then 'sl' end), '') end as seiten,
         regexp_match(o.nz, 'TP ([0-9.]+) brächte ([0-9]+) \$ > Ziel ([0-9]+) \$ → ([0-9.]+)') as tp_m,
         regexp_match(o.nz, 'SL ([0-9.]+) kostete −([0-9]+) \$ > Grenze ([0-9]+) \$ → ([0-9.]+)') as sl_m,
         substring(o.tr from '([0-9]+\.[0-9]+)s·Endprüfung')::numeric as t0,
         substring(o.tr from '([0-9]+\.[0-9]+)s·Nachziehen am Fill: ')::numeric as t1
  from orbit o
),
orbit_e as (
  select z.*,
         case when z.nz ~ '^(kein Fill|kein Punktwert|Soll nicht rechenbar)' then 'abgebrochen'
              when z.seiten is null then 'nicht_noetig'
              when z.nz ~ 'nicht geändert|abgebrochen \(|— prüfen|nicht aktiv|Frist um' then 'abgebrochen'
              when z.nz ~ '✓' then 'nachgezogen'
              else 'unklar' end as ergebnis
  from orbit_z z
),
orbit_f as (
  select z.at_utc, z.user_id, z.plan_id, 'orbit'::text as route,
         nullif(concat_ws('+', case when z.nz ~ 'Ziel [0-9]' then 'ziel' end, case when z.nz ~ 'Grenze [0-9]|kein Stop gelesen' then 'tagesgrenze' end), '') as ausloeser,
         case z.seiten when 'tp' then 'tp' when 'sl' then 'sl' when 'tp+sl' then 'beide' end as seite,
         z.ergebnis,
         case z.ergebnis
           when 'abgebrochen' then coalesce(substring(z.nz from '((TP|SL): [^·]*(nicht geändert|Frist um|prüfen)[^·]*)'),
                                            substring(z.nz from '(Reiter Orders nicht aktiv[^·]*|abgebrochen \([^)]*\))'), left(z.nz, 200))
           else left(z.nz, 300) end as grund,
         round(z.t1 - z.t0, 1) as dauer_s, false as dauer_ca,
         nullif(coalesce((z.tp_m)[2]::numeric - (z.tp_m)[3]::numeric, 0) + coalesce((z.sl_m)[2]::numeric - (z.sl_m)[3]::numeric, 0), 0) as abweichung_vorher_usd,
         case z.ergebnis
           when 'nachgezogen' then 0 when 'unklar' then null
           else nullif(coalesce((z.tp_m)[2]::numeric - (z.tp_m)[3]::numeric, 0) + coalesce((z.sl_m)[2]::numeric - (z.sl_m)[3]::numeric, 0), 0) end as abweichung_nachher_usd,
         nullif(concat_ws(' / ', 'SL ' || (z.sl_m)[1], 'TP ' || (z.tp_m)[1]), '') as levels_vorher,
         nullif(concat_ws(' / ', 'SL ' || (z.sl_m)[4], 'TP ' || (z.tp_m)[4]), '') as levels_nachher,
         (select count(*) from regexp_matches(z.tr, 'Ändern-Ansicht ''', 'g'))::int as aendern_dialoge,
         null::int as aendern_punkte,
         case when z.seiten is not null then 1 end as versuche,
         z.nz ~ 'Frist um' as frist_erreicht,
         z.pc, z.id::text as quelle_id
  from orbit_e z
),
polar as (
  select l.id, l.plan_id, l.slave_user_id as user_id, l.slave->'level' as lv,
         (select (x->>'at_ms')::bigint from jsonb_array_elements(case when jsonb_typeof(l.slave->'schritte') = 'array' then l.slave->'schritte' else '[]' end) x
           where x->>'phase' = 'gefuellt' limit 1) as ms0,
         (select (x->>'at_ms')::bigint from jsonb_array_elements(case when jsonb_typeof(l.slave->'schritte') = 'array' then l.slave->'schritte' else '[]' end) x
           where x->>'phase' = 'level' limit 1) as ms1,
         coalesce(l.updated_at, l.created_at) as at_lauf
  from public.polar_lauf l
  where jsonb_typeof(l.slave->'level') = 'object'
),
polar_f as (
  select coalesce(to_timestamp(z.ms1 / 1000.0), z.at_lauf) as at_utc, z.user_id, z.plan_id::text as plan_id, 'polar'::text as route,
         coalesce(z.lv->>'quelle', 'plan') as ausloeser, 'beide'::text as seite,
         case when z.lv->>'quelle' = 'notfall' or z.lv->>'ok' = 'false' then 'abgebrochen' when z.lv->>'ok' = 'true' then 'nachgezogen' else 'unklar' end as ergebnis,
         case when z.lv->>'quelle' = 'notfall' then 'Airbag übersprungen — Notfall-Level aus dem F9 bleiben'
              when z.lv->>'ok' = 'false' then 'SL/TP nicht per API bestätigt'
              else nullif(z.lv->>'grund', '') end as grund,
         round((z.ms1 - z.ms0) / 1000.0, 1) as dauer_s, false as dauer_ca,
         null::numeric as abweichung_vorher_usd, null::numeric as abweichung_nachher_usd,
         'SL ' || (z.lv->'notfall'->>'sl') || ' / TP ' || (z.lv->'notfall'->>'tp') as levels_vorher,
         'SL ' || (z.lv->>'sl') || ' / TP ' || (z.lv->>'tp') as levels_nachher,
         null::int as aendern_dialoge, null::int as aendern_punkte, 1 as versuche, null::boolean as frist_erreicht,
         null::text as pc, z.id::text as quelle_id
  from polar z
),
alle as (
  select * from echo_f union all select * from orbit_f union all select * from polar_f
)
select (a.at_utc at time zone 'Asia/Dubai') as at, a.at_utc, (a.at_utc at time zone 'Asia/Dubai')::date as tag,
       g.mitglied as wer, g.gruppe, a.user_id, a.plan_id, a.route, a.ausloeser, a.seite, a.ergebnis, a.grund, a.dauer_s, a.dauer_ca,
       a.abweichung_vorher_usd, a.abweichung_nachher_usd, a.levels_vorher, a.levels_nachher,
       a.aendern_dialoge, a.aendern_punkte, a.versuche, a.frist_erreicht, a.pc, a.quelle_id
from alle a
left join lateral (select x.mitglied, x.gruppe from public.id_gruppen_uebersicht x where x.user_id = a.user_id
                   order by (x.gruppe = 'Hermann Technologies') desc limit 1) g on true;

-- Statistik je Dubai-Tag × Route × Ergebnis, nur IDs der Gruppe „Hermann Technologies" (Memory prophos-amir-nicht-ht).
-- trefferquote_pct = nachgezogen / (nachgezogen + abgebrochen) des Tages × Route — „nicht_noetig" und „unklar" zählen nicht mit.
create or replace view public.justage_statistik with (security_invoker = true) as
with e as (
  select * from public.justage_ereignisse where gruppe = 'Hermann Technologies'
),
je_route as (
  select tag, route,
         count(*) filter (where ergebnis = 'nachgezogen') as n_ok,
         count(*) filter (where ergebnis = 'abgebrochen') as n_ab
  from e group by tag, route
)
select e.tag, e.route, e.ergebnis, count(*) as anzahl,
       case when r.n_ok + r.n_ab > 0 then round(100.0 * r.n_ok / (r.n_ok + r.n_ab), 0) end as trefferquote_pct,
       round(avg(e.dauer_s), 1) as dauer_s_avg, max(e.dauer_s) as dauer_s_max,
       round(avg(e.abweichung_vorher_usd), 0) as abweichung_vorher_usd_avg,
       sum(coalesce(e.aendern_dialoge, 0)) as aendern_dialoge,
       count(*) filter (where e.frist_erreicht) as frist_erreicht,
       string_agg(distinct e.ausloeser, ', ') as ausloeser
from e join je_route r on r.tag = e.tag and r.route = e.route
group by e.tag, e.route, e.ergebnis, r.n_ok, r.n_ab;

-- RÜCKBAU (nichts sonst hängt an den Views):
-- drop view if exists public.justage_statistik;
-- drop view if exists public.justage_ereignisse;

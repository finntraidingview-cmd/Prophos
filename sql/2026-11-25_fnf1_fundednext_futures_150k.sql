-- FNF1 (25.11.2026, Slave 3) · FundedNext Futures 150k Challenge (Flex) im Challenge-Planer für HT + letzter Trade mit Gegenhedge wie Tradeify/Lucid.
-- Finn (über den Master): „FundedNext Futures 150k Challenge einschalten, und letzter Trade mit Hedge wie immer“. Screenshot: Ziel 8.000 $, Max Loss EOD
-- 4.000 $, kein Daily Loss, Consistency 40 %, Reset 284,99 $, max. 8 Minis / 80 Micros. Die Regel (namen fundednextfutures, tvv2, 150k: dd 4.000,
-- Ziel 5,333 %, TP 3.050–3.150, tp_max 3.200, kein SL, lock_bei_start) bleibt — außer Kontrakte: 1–2 NQ statt 2–3 (Finn: „immer 1–2 NQ, nie 3“).
--
-- NICHT EINGESPIELT — ERST NACH dem Backend-Push mit FNF1 (app.py tfh_param/tfh_firma kennen 'fundednextfutures'). Vorher eingespielt würde ein altes
-- Backend den finalen FNF-Trade NICHT markieren (hedge_art), der Halte-Riegel griffe nicht → der letzte Trade liefe ohne Gegenhedge.
--
-- Was diese Datei tut (Tradeify und Lucid bleiben bitgleich):
--   1. Sicherung der Regel-Zeile (fnf1_auto_plan_regeln_20261125, RLS an, Rechte entzogen).
--   2. prophos_final_hedge_firmen() / prophos_final_hedge_firma(): 'FundedNext Futures' wie 'Lucid Trading' — nur wenn regeln.tradeify_final_hedge.firmen
--      'fundednextfutures' enthält UND der Plan die Marke hedge_art 'tradeify_final' trägt (setzt nur Railway tfh_tick, nur HT-IDs, nie Orbit Prio 2) →
--      Emins FundedNext Futures (firmen_modell orbit_prio2, Marke 'apex') bleibt unberührt. Die drei Riegel (trade_plans_a_final_halten,
--      trade_plans_ein_finaler + prophos_ein_finaler_frei, trade_plans_kontoart_weg) rufen diese Funktion schon (LF1) — kein Patch daran nötig.
--   3. auto_plan_regeln id 1 (Standard = HT): tradeify_final_hedge.firmen += 'fundednextfutures'; FundedNext Futures planen → true, kauf_eur 150000 → 245,
--      150k menge [1, 2] + puffer_je_menge {1, 2}.
--      Emin: eigene Zeile auto_plan_gruppe mit firmen_modell fundednextfutures = orbit_prio2 (plant dort ohnehin, Modell bleibt); Emin hat keine 150k.
-- Idempotent: zweimal einspielen ändert nichts. Rückbau unten (auskommentiert).

begin;

create table if not exists fnf1_auto_plan_regeln_20261125 as
  select id, regeln, updated_at, now() as gesichert_at from public.auto_plan_regeln where id = 1;
alter table fnf1_auto_plan_regeln_20261125 enable row level security;
revoke all on fnf1_auto_plan_regeln_20261125 from public, anon, authenticated;

create or replace function public.prophos_final_hedge_firmen()
returns text[] language sql stable security definer set search_path = public as $$
  select array['Tradeify']
         || case when coalesce((select (r.regeln->'tradeify_final_hedge'->'firmen') ? 'lucid'
                                  from public.auto_plan_regeln r where r.id = 1), false)
                 then array['Lucid Trading'] else array[]::text[] end
         || case when coalesce((select (r.regeln->'tradeify_final_hedge'->'firmen') ? 'fundednextfutures'
                                  from public.auto_plan_regeln r where r.id = 1), false)
                 then array['FundedNext Futures'] else array[]::text[] end
$$;

create or replace function public.prophos_final_hedge_firma(p_firm text, p_hedge_art text)
returns boolean language sql stable security definer set search_path = public as $$
  select case public.prophos_firma_key(p_firm)
           when 'Tradeify' then true
           when 'Lucid Trading' then coalesce(p_hedge_art, '') = 'tradeify_final' and 'Lucid Trading' = any(public.prophos_final_hedge_firmen())
           when 'FundedNext Futures' then coalesce(p_hedge_art, '') = 'tradeify_final' and 'FundedNext Futures' = any(public.prophos_final_hedge_firmen())
           else false end
$$;

revoke all on function public.prophos_final_hedge_firmen() from public, anon, authenticated;
revoke all on function public.prophos_final_hedge_firma(text, text) from public, anon, authenticated;

-- Final-Weg: FundedNext Futures dazu (Tradeify/Lucid bleiben)
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{tradeify_final_hedge,firmen}',
                          coalesce(r.regeln->'tradeify_final_hedge'->'firmen', '["tradeify"]'::jsonb) || '["fundednextfutures"]'::jsonb),
       updated_at = now()
 where r.id = 1
   and jsonb_typeof(r.regeln->'tradeify_final_hedge') = 'object'
   and not coalesce((r.regeln->'tradeify_final_hedge'->'firmen') ? 'fundednextfutures', false);

-- FundedNext Futures: planen an, Kauf 150k 245 € (50k bleibt 74), Finn-Nachtrag „immer 1–2 NQ, nie 3“: phasen.challenge (= 150k; 50k hat eigene
-- je_groesse-Werte 1 NQ und bleibt) menge [1, 2], puffer_je_menge 1 und 2 NQ je 15–25 $ (wie FNF 50k / Tradeify 2 NQ; der letzte Futures-Trade rechnet
-- ohnehin 20 $ je Kontrakt, AP_PUFFER_JE_KT_FUT)
update public.auto_plan_regeln r
   set regeln = jsonb_set(jsonb_set(jsonb_set(jsonb_set(r.regeln,
                  array['firmen', (x.i - 1)::text, 'planen'], 'true'::jsonb),
                  array['firmen', (x.i - 1)::text, 'kauf_eur', '150000'], '245'::jsonb),
                  array['firmen', (x.i - 1)::text, 'phasen', 'challenge', 'menge'], '[1, 2]'::jsonb),
                  array['firmen', (x.i - 1)::text, 'phasen', 'challenge', 'puffer_je_menge'], '{"1": [15, 25], "2": [15, 25]}'::jsonb),
       updated_at = now()
  from (select f.i from public.auto_plan_regeln r2, jsonb_array_elements(r2.regeln->'firmen') with ordinality f(v, i)
         where r2.id = 1 and f.v->'namen' ? 'fundednextfutures') x
 where r.id = 1
   and jsonb_typeof(r.regeln->'firmen'->(x.i - 1)::int->'kauf_eur') = 'object'
   and jsonb_typeof(r.regeln->'firmen'->(x.i - 1)::int->'phasen'->'challenge') = 'object'
   and ((r.regeln->'firmen'->(x.i - 1)::int->>'planen') is distinct from 'true'
        or (r.regeln->'firmen'->(x.i - 1)::int->'kauf_eur'->>'150000') is distinct from '245'
        or (r.regeln->'firmen'->(x.i - 1)::int->'phasen'->'challenge'->'menge') is distinct from '[1, 2]'::jsonb
        or (r.regeln->'firmen'->(x.i - 1)::int->'phasen'->'challenge'->'puffer_je_menge') is distinct from '{"1": [15, 25], "2": [15, 25]}'::jsonb);

commit;

-- Prüfen:
-- select public.prophos_final_hedge_firmen();                                            -- {Tradeify,"Lucid Trading","FundedNext Futures"}
-- select public.prophos_final_hedge_firma('FundedNext Futures', 'tradeify_final'),        -- true
--        public.prophos_final_hedge_firma('FundedNext Futures', 'apex'),                  -- false (Emin, Orbit Prio 2)
--        public.prophos_final_hedge_firma('FundedNext', 'tradeify_final'),                -- false (CFD)
--        public.prophos_final_hedge_firma('Lucid Trading', 'tradeify_final');             -- true (wie bisher)
-- select f->'planen', f->'kauf_eur', r.regeln->'tradeify_final_hedge'->'firmen' from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') f
--  where r.id = 1 and f->'namen' ? 'fundednextfutures';                                  -- true, {"50000": 74, "150000": 245}, ["tradeify","lucid","fundednextfutures"]
-- select f->'phasen'->'challenge'->'menge', f->'phasen'->'challenge'->'puffer_je_menge', f->'je_groesse'->'50000'->'phasen'->'challenge'->'menge'
--   from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') f where r.id = 1 and f->'namen' ? 'fundednextfutures';
--                                                                                       -- [1, 2], {"1": [15, 25], "2": [15, 25]}, [1, 1] (50k unverändert)

-- Rückbau (nur falls nötig; Funktionen danach wieder mit dem LF1-Stand aus sql/2026-11-06_lucid_final_hedge.sql anlegen):
-- update public.auto_plan_regeln r set regeln = s.regeln, updated_at = now() from fnf1_auto_plan_regeln_20261125 s where r.id = s.id;

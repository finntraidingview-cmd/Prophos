-- LF1 (06.11.2026, Slave 9) · Lucid-Final-Trade mit Gegenhedge genau wie Tradeify (Finn: „der letzte Trade bei Lucid komplett genau gleich wie bei
-- Tradeify"; Entscheidung über den Master: Kauf Lucid 150k 170 €, Hedge 1:1 (netto_faktor 1, wie Tradeify live), ein finaler je ID, nur HT).
-- NICHT EINGESPIELT — MIT dem Backend-Push (app.py tfh_tick kennt die Firmenliste) und nur auf Finns/Masters Wort.
--
-- Was diese Datei tut (Tradeify bleibt bitgleich):
--   1. prophos_final_hedge_firmen() / prophos_final_hedge_firma(firma, hedge_art): Tradeify immer; Lucid nur, wenn regeln.tradeify_final_hedge.firmen
--      'lucid' enthält UND der Plan die Marke hedge_art 'tradeify_final' trägt (setzt nur Railway tfh_tick, nur HT, nie Orbit Prio 2) →
--      Emins Lucid (orbit_prio2, Marke 'apex') bleibt unberührt.
--   2. Drei Riegel lesen statt „Firma = Tradeify" diese Funktion (Patch genau einer Stelle je Funktion, geprüft):
--      trade_plans_a_final_halten (nie ohne Hedge starten), trade_plans_ein_finaler + prophos_ein_finaler_frei (ein finaler je ID),
--      trade_plans_kontoart_weg (Challenge + Orbit V3 + tradeify_hedge 'mit' erlaubt). Texte: Firmenname statt fest „Tradeify" — für Tradeify gleich.
--   3. auto_plan_regeln: tradeify_final_hedge.firmen = ["tradeify","lucid"], Lucid kauf_eur 150000 = 170 (vorher 222; 50k bleibt 78).
-- Idempotent: zweimal einspielen ändert nichts. Rückbau: sql/2026-11-06_lucid_final_hedge_rueckbau.sql.

begin;

create or replace function public.prophos_final_hedge_firmen()
returns text[] language sql stable security definer set search_path = public as $$
  select array['Tradeify'] || case when coalesce((select (r.regeln->'tradeify_final_hedge'->'firmen') ? 'lucid'
                                                    from public.auto_plan_regeln r where r.id = 1), false)
                                   then array['Lucid Trading'] else array[]::text[] end
$$;

create or replace function public.prophos_final_hedge_firma(p_firm text, p_hedge_art text)
returns boolean language sql stable security definer set search_path = public as $$
  select case public.prophos_firma_key(p_firm)
           when 'Tradeify' then true
           when 'Lucid Trading' then coalesce(p_hedge_art, '') = 'tradeify_final' and 'Lucid Trading' = any(public.prophos_final_hedge_firmen())
           else false end
$$;

revoke all on function public.prophos_final_hedge_firmen() from public, anon, authenticated;
revoke all on function public.prophos_final_hedge_firma(text, text) from public, anon, authenticated;

-- Patch: genau eine Stelle je (alt → neu); schon gepatcht → nichts; weder alt noch neu → Abbruch (Definition hat sich geändert, nicht raten)
do $patch$
declare
  r record;
  def text;
  n_alt int;
begin
  for r in select * from (values
    ('trade_plans_a_final_halten',
     $a$  if public.prophos_firma_key(new.master_firm) is distinct from public.prophos_firma_key('Tradeify') then$a$,
     $b$  if not public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art') then$b$),
    ('trade_plans_a_final_halten',
     $a$  txt := 'finaler Tradeify-Trade wartet auf Gegenhedge (TP '$a$,
     $b$  txt := 'finaler ' || public.prophos_firma_key(new.master_firm) || '-Trade wartet auf Gegenhedge (TP '$b$),
    ('trade_plans_a_final_halten',
     $a$'[finaler Tradeify gehalten] ' || txt$a$,
     $b$'[finaler ' || public.prophos_firma_key(new.master_firm) || ' gehalten] ' || txt$b$),
    ('trade_plans_ein_finaler',
     $a$if k is null or not (k = any(public.prophos_ein_finaler_firmen())) then$a$,
     $b$if k is null or not (k = any(public.prophos_ein_finaler_firmen()) or public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art')) then$b$),
    ('trade_plans_ein_finaler',
     $a$'[ein finaler Tradeify je ID] ' || txt$a$,
     $b$'[ein finaler ' || k || ' je ID] ' || txt$b$),
    ('prophos_ein_finaler_frei',
     $a$  select id, user_id, master_firm, status into pl from public.trade_plans where id = p_plan;$a$,
     $b$  select id, user_id, master_firm, status, mt5_baseline->>'hedge_art' as hedge_art into pl from public.trade_plans where id = p_plan;$b$),
    ('prophos_ein_finaler_frei',
     $a$  if pl.user_id is null or k is null or not (k = any(public.prophos_ein_finaler_firmen())) then$a$,
     $b$  if pl.user_id is null or k is null or not (k = any(public.prophos_ein_finaler_firmen()) or public.prophos_final_hedge_firma(pl.master_firm, pl.hedge_art)) then$b$),
    ('prophos_ein_finaler_frei',
     $a$     and public.prophos_firma_key(p.master_firm) = k
$a$,
     $b$     and public.prophos_firma_key(p.master_firm) = k
     and (k = any(public.prophos_ein_finaler_firmen()) or coalesce(p.mt5_baseline->>'hedge_art', '') = 'tradeify_final')
$b$),
    ('trade_plans_kontoart_weg',
     $a$     and public.prophos_firma_key(new.master_firm) = public.prophos_firma_key('Tradeify')
$a$,
     $b$     and public.prophos_final_hedge_firma(new.master_firm, new.mt5_baseline->>'hedge_art')
$b$)
  ) as t(fn, alt, neu)
  loop
    select pg_get_functiondef(p.oid) into def from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = r.fn;
    if def is null then
      raise exception 'LF1: Funktion % fehlt', r.fn;
    end if;
    if strpos(def, r.neu) > 0 then
      continue;                                   -- schon gepatcht
    end if;
    n_alt := (length(def) - length(replace(def, r.alt, ''))) / length(r.alt);
    if n_alt <> 1 then
      raise exception 'LF1: % — Stelle % mal gefunden (erwartet 1): %', r.fn, n_alt, left(r.alt, 80);
    end if;
    execute replace(def, r.alt, r.neu);
  end loop;
end
$patch$;

-- Regeln: Lucid in den Final-Weg, Kauf Lucid 150k 170 € (Finn); 50k bleibt 78
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{tradeify_final_hedge}',
                          coalesce(r.regeln->'tradeify_final_hedge', '{}'::jsonb) || '{"firmen": ["tradeify", "lucid"]}'::jsonb),
       updated_at = now()
 where r.id = 1
   and not coalesce((r.regeln->'tradeify_final_hedge'->'firmen') ? 'lucid', false);

update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, array['firmen', (x.i - 1)::text, 'kauf_eur', '150000'], '170'::jsonb),
       updated_at = now()
  from (select f.i from public.auto_plan_regeln r2, jsonb_array_elements(r2.regeln->'firmen') with ordinality f(v, i)
         where r2.id = 1 and f.v->'namen' ? 'lucidtrading') x
 where r.id = 1
   and jsonb_typeof(r.regeln->'firmen'->(x.i - 1)::int->'kauf_eur') = 'object'
   and (r.regeln->'firmen'->(x.i - 1)::int->'kauf_eur'->>'150000') is distinct from '170';

commit;

-- Prüfen:
-- select public.prophos_final_hedge_firmen();                                         -- {Tradeify,"Lucid Trading"}
-- select public.prophos_final_hedge_firma('Lucid Trading', 'tradeify_final'),          -- true
--        public.prophos_final_hedge_firma('Lucid Trading', 'apex'),                    -- false (Emin, Orbit Prio 2)
--        public.prophos_final_hedge_firma('Tradeify', null);                           -- true (wie bisher)
-- select f->'kauf_eur', r.regeln->'tradeify_final_hedge'->'firmen' from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') f
--  where r.id = 1 and f->'namen' ? 'lucidtrading';                                     -- {"50000": 78, "150000": 170}, ["tradeify","lucid"]

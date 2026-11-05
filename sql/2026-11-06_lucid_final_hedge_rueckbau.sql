-- LF1 RÜCKBAU (06.11.2026, Slave 9) zu sql/2026-11-06_lucid_final_hedge.sql — stellt die drei Riegel, die Regeln und den Lucid-Kauf von vorher her.
-- NICHT EINGESPIELT. Erst den Backend-Stand ohne LF1 ausliefern oder Lucid vorher über den Schalter aus der Firmenliste nehmen.
-- Idempotent: schon zurückgebaut → nichts.

begin;

do $patch$
declare
  r record;
  def text;
  n_neu int;
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
      raise exception 'LF1-Rückbau: Funktion % fehlt', r.fn;
    end if;
    if strpos(def, r.neu) = 0 then
      continue;                                   -- schon zurückgebaut
    end if;
    n_neu := (length(def) - length(replace(def, r.neu, ''))) / length(r.neu);
    if n_neu <> 1 then
      raise exception 'LF1-Rückbau: % — neue Stelle % mal gefunden (erwartet 1): %', r.fn, n_neu, left(r.neu, 80);
    end if;
    execute replace(def, r.neu, r.alt);
  end loop;
end
$patch$;

drop function if exists public.prophos_final_hedge_firma(text, text);
drop function if exists public.prophos_final_hedge_firmen();

update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{tradeify_final_hedge}', (r.regeln->'tradeify_final_hedge') - 'firmen'), updated_at = now()
 where r.id = 1 and (r.regeln->'tradeify_final_hedge') ? 'firmen';

update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, array['firmen', (x.i - 1)::text, 'kauf_eur', '150000'], '222'::jsonb),
       updated_at = now()
  from (select f.i from public.auto_plan_regeln r2, jsonb_array_elements(r2.regeln->'firmen') with ordinality f(v, i)
         where r2.id = 1 and f.v->'namen' ? 'lucidtrading') x
 where r.id = 1
   and (r.regeln->'firmen'->(x.i - 1)::int->'kauf_eur'->>'150000') = '170';

commit;

-- UNT5 (05.11.2026, Master/Finn: „Finn + Pascal sehen als HT-Admins nichts von Emin, und Emin sieht nichts von HT") — NICHT eingespielt (Master, auf Finns Wort).
-- wd_konten_alle() (security definer, RPC aus prophos.html wdDatenLaden) lieferte JEDEM Login alle Winning-Day-Konten aller IDs mit Personenname,
-- External ID und Balance (live 05.11.: 37 WD-Konten, 2 davon Emin). Neu: nur Konten aus dem eigenen Unternehmen (prophos_gruppe_von wie Firmen-Abstand/
-- Gegenhedge/Notizzettel); eine ID ohne Unternehmen (null) sieht nur ihre eigenen. Spalten, Rechnung und Reihenfolge unverändert. anon verliert EXECUTE
-- (lieferte ohne Login ohnehin nichts). Railway liest mit dem Service-Key über eigene Wege — unberührt.
-- FOLGE (S2, G3-Bewertung): Finns Mac sieht im WD-Farmer Emins WD-Konten nicht mehr — Emins WD-Pläne legt dann nur noch Emins eigener Mac/Tab an
-- (wdPlaeneAnlegen). Darum zusammen mit G3 Abschnitt 4 (wd_tagesplan lesen) und erst nach Finns Ja einspielen.
-- Live-md5 vorher: 62d4b9ecdb11a7a852cccf86f309e35d. Rückbau: sql/2026-11-05_unt5_wd_konten_alle_rueckbau.sql.
begin;
CREATE OR REPLACE FUNCTION public.wd_konten_alle()
 RETURNS TABLE(id uuid, user_id uuid, person text, name text, firm text, account_type text, external_id text, max_drawdown numeric, balance numeric, wd_farm boolean, max_profit_per_trade numeric, max_loss_per_trade numeric, wd_tp numeric, wd_sl numeric, goal_kind text, goal_target integer, goal_done_offset integer, goal_manual boolean, goal_since text, winning_days integer, live_balance numeric, live_ccy text, live_at timestamp with time zone, starting_balance numeric)
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  with tage as (
    select p.master_account_id::text as acc,
           (coalesce(p.ended_at, p.started_at, p.completed_at, p.created_at) at time zone 'Europe/Berlin')::date as tag,
           sum(p.master_pl) as pl
      from public.trade_plans p
     where p.status in ('completed', 'review') and p.master_pl is not null
     group by 1, 2
  ), live as (
    select x->>'login' as login, (x->>'balance')::numeric as bal, x->>'ccy' as ccy, d.updated_at
      from public.dup_live d, jsonb_array_elements(coalesce(d.accounts, '[]'::jsonb)) x
     where x->>'login' is not null
  ), basis as (
    select a.*,
           coalesce(nullif(u.raw_user_meta_data->>'name', ''), split_part(coalesce(u.email, ''), '@', 1)) as person,
           (select l.bal from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_bal,
           (select l.ccy from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_ccy,
           (select l.updated_at from live l where l.login = a.external_id order by l.updated_at desc nulls last limit 1) as dup_at
      from public.accounts a
      left join auth.users u on u.id = a.user_id
     where auth.uid() is not null and a.account_type = 'winning_days'
       -- UNT5: nur das eigene Unternehmen (derselbe Schlüssel wie die DB-Riegel); ohne Unternehmen (null) = nur die eigene ID
       and (a.user_id = auth.uid()
            or (public.prophos_gruppe_von(auth.uid()) is not null
                and public.prophos_gruppe_von(a.user_id) = public.prophos_gruppe_von(auth.uid())))
  )
  select b.id, b.user_id, b.person, b.name, b.firm, b.account_type, b.external_id, b.max_drawdown, b.balance, b.wd_farm,
         b.max_profit_per_trade, b.max_loss_per_trade, b.wd_tp, b.wd_sl, b.goal_kind, b.goal_target, b.goal_done_offset, b.goal_manual,
         b.goal_since::text,
         (case when b.goal_manual then coalesce(b.goal_done_offset, 0)
               else coalesce(b.goal_done_offset, 0) + (select count(*) from tage t where t.acc = b.id::text and t.pl > coalesce(b.goal_min_profit, 0)
                                                        and (b.goal_since is null or t.tag >= b.goal_since::date)) end)::integer as winning_days,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then b.tv_balance else b.dup_bal end as live_balance,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then 'USD' else b.dup_ccy end as live_ccy,
         case when b.tv_balance is not null and (b.dup_at is null or b.tv_balance_at >= b.dup_at) then b.tv_balance_at else b.dup_at end as live_at,
         b.starting_balance
    from basis b
$function$;
revoke execute on function public.wd_konten_alle() from anon;
grant execute on function public.wd_konten_alle() to authenticated;
commit;

-- Kontrolle (als Login, nur lesen):
--   set local role authenticated; select set_config('request.jwt.claims', json_build_object('sub','<uid>','role','authenticated')::text, true);
--   select count(*), count(*) filter (where public.prophos_gruppe_von(user_id) is distinct from public.prophos_gruppe_von('<uid>'::uuid)) fremd from public.wd_konten_alle();
--   SOLL: fremd = 0; Finn + Pascal = alle HT-WD-Konten (35 am 05.11.), Emin = 2.
-- select has_function_privilege('anon', 'public.wd_konten_alle()', 'execute');   -- false

-- Moritz FTMO 100k 511464160 (Phase 1, accounts b1051f42) ist GEBLOWT. Finn 18.11.2026 ~04:20 Dubai: „ja dann is er geblowed, dann soll er zu geblowed kommen“.
-- Beleg: Echo-Start 17.11. 06:57 Dubai (Plan b5927c8a, SELL) → „Handel am Konto gesperrt (account_info.trade_allowed = False)“, Lesung 89.987,18 $
-- < Boden 90.000 $ (10 % Max Loss). Der Plan selbst hat nie eine Order platziert (stand nach dem Tages-Reset im Abhaken als „nie gestartet“).
-- Gleicher Schreibweg wie Radar „Abhaken → geblowt“ / _ap_blow_auto_abhaken: Plan completed + blown (P&L dieses Plans 0 — nie gefüllt, kein Echo-Hedge
-- eröffnet), Konto ins Archiv des Besitzers (user_settings 'archive', reason 'blown') wie _konto_archiv_eintragen + Echo-Löschauftrag über mt5_links.
-- Guards: Plan nur aus review; Archiv-Eintrag nur, wenn noch nicht archiviert.

begin;

update public.trade_plans p
set status = 'completed', blown = true, master_pl = 0, slave_pl = 0, pl_quelle = 'hand',
    completed_at = now(), ended_at = coalesce(p.ended_at, now()),
    mt5_baseline = coalesce(p.mt5_baseline, '{}'::jsonb)
      || jsonb_build_object('final', coalesce(p.mt5_baseline->'final', '{}'::jsonb)
           || jsonb_build_object('today_pnl', 0, 'datum', '2026-11-17', 'at', now(), 'quelle', 'hand',
                                 'grund', 'geblowt (Finn 18.11.2026: Konto unter Boden 90.000 $, Handel gesperrt; Plan nie gefüllt)'))
where p.id::text like 'b5927c8a%' and p.status = 'review' and p.started_at is null;

insert into public.user_settings (user_id, key, value, updated_at)
select 'aff98e60-e9a0-4821-9d1d-31634571a2f4', 'archive', '{}'::jsonb, now()
where not exists (select 1 from public.user_settings where user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and key = 'archive');

update public.user_settings s
set value = coalesce(s.value, '{}'::jsonb) || jsonb_build_object('b1051f42-4e15-4332-b07f-19b9e1360ba4',
              jsonb_build_object('archived', true, 'reason', 'blown', 'at', now())),
    updated_at = now()
where s.user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and s.key = 'archive'
  and not coalesce((s.value->'b1051f42-4e15-4332-b07f-19b9e1360ba4'->>'archived')::boolean, false);

insert into public.echo_loesch_auftraege (mt5_login, grund, account_name, angelegt_am, erledigt_am, erledigt_info)
select ml.mt5_login::text, 'blown', '100k 511464160 → Phase 1', now(), null, null
from public.mt5_links ml where ml.account_id = 'b1051f42-4e15-4332-b07f-19b9e1360ba4' and ml.mt5_login is not null
limit 1
on conflict (mt5_login) do update set grund = excluded.grund, account_name = excluded.account_name, angelegt_am = excluded.angelegt_am,
                                      erledigt_am = null, erledigt_info = null;

commit;

-- Kontrolle:
-- select status, blown, master_pl from trade_plans where id::text like 'b5927c8a%';
-- select value->'b1051f42-4e15-4332-b07f-19b9e1360ba4' from user_settings where user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and key = 'archive';

-- WINNING DAYS AUTOMATISCH (Finn 03.11.2026 ~01:35 Dubai über den Eingang: „kannst du das umbauen … dass es in Zukunft immer zählt“; Fall Mike Apex 100k
-- …0002: drei Gewinn-Tage, gezählt 2). Code: app.py wd_auto_* / prophos.html zielWdAuto. Stand = automatisch gezählte CME-Handelstage (Tagessumme der
-- Master-P&L ≥ Mindestgewinn: goal_min_profit, sonst Tradeify/Lucid/FundedNext Futures 250 $, Topstep 150 $, Apex 100k 300 $ / sonst 350 $, Tradeify CFD
-- und andere > 0) ab goal_wd_seit. Stand = |Auto-Tage ∪ goal_wd_hand_tage (Haken „war ein Winning Day“, CME-Tage)| + goal_wd_korrektur (±1 im Konto-Modal).
-- goal_done_offset bleibt als alter Stand stehen.
-- BESTAND (Eingang 03.11.2026): der heute angezeigte Stand bleibt bei JEDEM Konto genau erhalten — Korrektur = goal_done_offset − automatisch gezählte Tage.
-- Trocken gerechnet (S9 03.11.2026): HT winning_days 21 × 0, 1 × −5, 1 × −1, 3 × +1; HT funded 111 × 0, 19 mit Korrektur ≠ 0; 1 Challenge −1; dazu 11 Konten
-- außerhalb HT. Darunter Chris Apex WD …0005 −1, Marc Apex 150k WD …0002 +1, Chris Tradeify WD …4657 −5 — bis Finn entscheidet. Ab dann zählt jeder neue
-- Gewinn-Tag von selbst. Zyklus-Start = letzte Payout-Anfrage (pending_payouts.created_at), sonst managed_payouts / Buchung, sonst Konto-Anlage
-- (= Funded-Beginn; die Funded-Phase zählt mit, unabhängig vom Kontotyp — Finn 03.11.2026, Mike Apex …0002 3 statt 2).
-- UNMITTELBAR VOR dem Push einspielen (Gegenprüfung: eine Payout-Anfrage im alten Code setzt goal_wd_seit nicht neu). Fehlen die Spalten, gilt der alte Stand.
-- Nur der ERSTE Lauf setzt Werte (danach haben alle Konten goal_wd_korrektur gesetzt; spätere Läufe tun nichts — ein zweiter Lauf auf später
-- angelegten Konten mit null würde sonst ihren Stand verschieben).
alter table public.accounts add column if not exists goal_wd_korrektur integer;
alter table public.accounts add column if not exists goal_wd_seit timestamptz;
alter table public.accounts add column if not exists goal_wd_hand_tage jsonb;

with konten as (
  select a.* from public.accounts a
   where a.goal_wd_korrektur is null and coalesce(a.account_type, '') <> 'live'
     and not exists (select 1 from public.accounts x where x.goal_wd_korrektur is not null)   -- nur der erste Lauf
     and ((a.goal_kind = 'winning_days' and a.goal_manual)
          or (a.account_type in ('funded', 'winning_days') and a.firm ~* '(tradeify|apex|topstep|futur|mffu|lucid|alpha ?future)'
              and not (a.firm ~* 'tradeify' and a.firm ~* 'cfd')))
), zyk as (
  select k.id, coalesce((select max(p.created_at) from public.pending_payouts p where p.account_id = k.id),
                        (select max(m.payout_date)::timestamptz from public.managed_payouts m where m.account_id = k.id),
                        (select max(t.occurred_at)::timestamptz from public.transactions t where t.account_id = k.id and t.kind = 'payout'),
                        k.created_at) as seit
    from konten k
), minp as (
  select k.id, case when k.goal_min_profit > 0 then k.goal_min_profit
                    when lower(k.firm) like '%tradeify%' and lower(k.firm) like '%cfd%' then null
                    when lower(k.firm) like '%tradeify%' then 250
                    when lower(k.firm) like '%lucid%' then 250
                    when lower(k.firm) like '%fundednext futures%' then 250
                    when lower(k.firm) like '%topstep%' then 150
                    when lower(k.firm) like '%apex%' then (case when substring(k.name from '(?i)(\d{2,3})\s*k\M') = '100' then 300 else 350 end)
                    else null end as m
    from konten k
), tage as (
  select p.master_account_id as id, (((coalesce(p.ended_at, p.completed_at)) + interval '7 hours') at time zone 'America/Chicago')::date as tag, sum(p.master_pl) as summe
    from public.trade_plans p join zyk z on z.id = p.master_account_id
   where p.status in ('completed', 'review') and p.master_pl is not null and coalesce(p.ended_at, p.completed_at) >= z.seit
   group by 1, 2
), auto as (
  select k.id, (select count(*) from tage t, minp mp where t.id = k.id and mp.id = k.id and (case when mp.m is not null then t.summe >= mp.m else t.summe > 0 end)) as n
    from konten k
)
update public.accounts a
   set goal_wd_seit = z.seit,
       goal_wd_korrektur = coalesce(a.goal_done_offset, 0) - au.n
  from zyk z, auto au
 where a.id = z.id and au.id = a.id;

-- Neue Konten: goal_wd_korrektur null = 0, Zyklus ab Anlage (goal_wd_seit null → created_at). Kein Spalten-Default nötig.

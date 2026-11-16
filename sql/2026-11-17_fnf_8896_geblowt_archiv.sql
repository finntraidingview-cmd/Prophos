-- Finn + Pascal FundedNext Futures 150k …38896 (accounts 103c974d, Plan e7109578, WD BUY 2 MNQ, tvv2) ist GEBLOWT.
-- Finn 17.11.2026 ~03:20 Dubai (Screenshot Radar „Am Markt“, P&L −2.189 $ bei Liq −2.256 $): „der acc wurde geblowed bitte archivieren“.
-- Vorgeschichte: Fusion-Hedge 16.11. 14:51 UTC fälschlich geschlossen (FH2, +248,12 €), Finn ließ den WD danach ohne Hedge laufen
-- (sql/2026-11-16_e7109578_abgleich_aus.sql). Auf Fusion ist nichts mehr offen.
-- Gleicher Schreibweg wie der Radar-Knopf „Abhaken → geblowt“ (app.py PATCH /admin/wd-plaene erledigt, konto_status 'blown'):
--   (1) Plan completed + blown, master_pl = Liquidation (liq_balance_start 152.355,62 − liq_balance 150.100 = −2.255,62 $, Hand-Wert),
--       slave_pl = Fusion 248,12 €, mt5_baseline.final/live wie _wd_ende_upd.
--   (2) Buchung wd_hedge wie _wd_hedge_buchung (Schlüssel „Trade #e7109578 WD-Hedge“, Konto = Fusion 488579 des Besitzers), idempotent.
--   (3) Konto ins Archiv des Besitzers (user_settings 'archive', reason 'blown') wie _konto_archiv_eintragen; ein schon archiviertes bleibt.
-- Guards: nur solange der Plan noch open ist bzw. noch keine Buchung/kein Archiv-Eintrag existiert. Echo-Löschauftrag entfällt (Futures, kein Echo).

begin;

update public.trade_plans p
set status = 'completed', blown = true, master_pl = -2255.62, slave_pl = 248.12, pl_quelle = 'hand',
    completed_at = now(), ended_at = coalesce(p.ended_at, now()),
    mt5_baseline = p.mt5_baseline
      || jsonb_build_object('final', jsonb_build_object('today_pnl', -2255.62, 'datum', '2026-11-17', 'at', now(), 'quelle', 'hand',
                                                         'grund', 'geblowt (Finn 17.11.2026, Liquidation)'))
      || jsonb_build_object('live', coalesce(p.mt5_baseline->'live', '{}'::jsonb) || jsonb_build_object('offen', false, 'at', now()))
where p.id = 'e7109578-2462-415d-beaa-6013d51d2c62' and p.status = 'open';

insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated)
select '48f272b4-913e-4598-a06a-1dcc3d5679fb', a.id, a.name, coalesce(a.firm, 'Fusion Markets'), 'wd_hedge', 248.12, 'EUR', date '2026-11-16',
       'Trade #e7109578 WD-Hedge · Finn + Pascal · ' || a.name, true
from public.accounts a
where a.id = '85b1b2a1-8bf1-4c09-8bb1-b3e9520b8896'
  and not exists (select 1 from public.transactions t where t.kind = 'wd_hedge' and t.notes like 'Trade #e7109578 WD-Hedge%');

update public.user_settings s
set value = coalesce(s.value, '{}'::jsonb) || jsonb_build_object('103c974d-b311-4ac4-9175-93eb6faaa32a',
              jsonb_build_object('archived', true, 'reason', 'blown', 'at', now())),
    updated_at = now()
where s.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and s.key = 'archive'
  and not coalesce((s.value->'103c974d-b311-4ac4-9175-93eb6faaa32a'->>'archived')::boolean, false);

commit;

-- Kontrolle:
-- select status, blown, master_pl, slave_pl from trade_plans where id = 'e7109578-2462-415d-beaa-6013d51d2c62';
-- select amount, occurred_at, notes from transactions where notes like 'Trade #e7109578 WD-Hedge%';
-- select value->'103c974d-b311-4ac4-9175-93eb6faaa32a' from user_settings where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'archive';

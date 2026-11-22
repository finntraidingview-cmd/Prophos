-- AB1 (23.11.2026): fünf Radar-Zeilen abhaken, die Finn (ID „Finn + Pascal“) per Klick nicht abgehakt bekam.
-- Die SQL macht dieselben Schreibvorgänge wie PATCH /admin/wd-plaene {aktion:'erledigt'} (app.py admin_wd_plaene, Zweig „erledigt“:
-- _wd_erledigt_upd, _buchen, _archivieren → _konto_archiv_eintragen). Belegt wird so, wie der Radar vorbelegt:
--   1–3  nie gestartet (Tagesreset „unklar“): master_pl 0, kein Fusion-P&L, Konto bleibt. Ohne Vorbelegung schickt der Knopf pl_quelle 'hand'.
--        Bei 2) (Marc Topstep …6381, TopstepX-Dialog „Maximum Loss Limit“) bewusst NICHT geblowt — nur der Plan wird erledigt.
--   4    Moritz FundedNext …3608 (Echo, Funded CFD): P&L wie am Plan (−2.473,92 $ / Fusion +380,22 €), konto_status none, Konto bleibt Funded.
--        Route mt5 = Fusion-P&L nur am Plan (WD_FUSION_AM_PLAN), keine wd_hedge-Buchung.
--   5    Finn + Pascal Tradeify WD …0431 (Orbit, Recovery): P&L wie am Plan (−3.435,74 $ / Fusion +975,13 €), konto_status blown wie
--        „Alle archivieren“: Plan blown, wd_hedge-Buchung auf das Fusion-Konto der ID, Konto ins Archiv (reason 'blown').
-- Was der Knopf hier NICHT schreibt und diese SQL deshalb auch nicht: mt5_baseline (alle 5 haben schon ein final), ended_at (gesetzt),
-- konto_typ (gesetzt bzw. tsv2/mt5), Good Day (alle P&L ≤ 0), Echo-Löschauftrag (…0431 hat keinen mt5_links-Eintrag).
-- Idempotent: Pläne nur aus status 'review'. Buchung nur, wenn noch keine mit dem Schlüssel „Trade #<plan8> WD-Hedge“ existiert.
-- Archiv-Eintrag nur, wenn das Konto noch nicht archiviert ist.

begin;

-- 1) Marco · Topstep 150k …7245 (Nova) · nie gestartet 21.11.
update public.trade_plans
   set status = 'completed', master_pl = 0, slave_pl = null, pl_quelle = 'hand', completed_at = now()
 where id = 'e0c811c9-f135-4b28-9aa3-94172fb324a7' and status = 'review' and route = 'tsv2';

-- 2) Marc · Topstep 150k …6381 · nie gestartet 20.11. — NICHT geblowt
update public.trade_plans
   set status = 'completed', master_pl = 0, slave_pl = null, pl_quelle = 'hand', completed_at = now()
 where id = 'ae943cb2-6e99-412e-802a-bf821cc654db' and status = 'review' and route = 'tsv2';

-- 3) Marc · Topstep 150k …6187 · nie gestartet 19.11.
update public.trade_plans
   set status = 'completed', master_pl = 0, slave_pl = null, pl_quelle = 'hand', completed_at = now()
 where id = '7948da31-538c-4ec8-9a1a-a24d059b42f0' and status = 'review' and route = 'tsv2';

-- (1–3: _buchen löscht bei slave_pl null vorhandene wd_hedge-Buchungen zum Plan — es gibt keine, geprüft 23.11. ~03:20 Dubai)
delete from public.transactions
 where kind = 'wd_hedge' and auto_generated
   and (notes like 'Trade #e0c811c9 WD-Hedge%' or notes like 'Trade #ae943cb2 WD-Hedge%' or notes like 'Trade #7948da31 WD-Hedge%');

-- 4) Moritz · FundedNext 100k …3608 · Funded-Verlust, Konto bleibt Funded
update public.trade_plans
   set status = 'completed', master_pl = -2473.92, slave_pl = 380.22, completed_at = now()
 where id = '3256158c-196e-4c5e-b5cc-4d9b605e7e47' and status = 'review' and route = 'mt5';

-- 5) Finn + Pascal · Tradeify WD 150k …0431 · geblowt + archivieren
update public.trade_plans
   set status = 'completed', master_pl = -3435.74, slave_pl = 975.13, blown = true, completed_at = now()
 where id = '1158bc99-ef26-48c1-bab4-3e528029f927' and status = 'review' and route = 'tvv2';

-- 5b) Fusion-P&L als wd_hedge buchen (wie _wd_hedge_buchung: Konto = Fusion-Konto der ID mit Hedge-Login aus mt5_live des Hedge-PCs,
--     hier „Fusion Echo Slave“ 85b1b2a1…; occurred_at = UTC-Datum wie jetzt.date() im Backend; Person = Anzeigename der ID)
insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated)
select '48f272b4-913e-4598-a06a-1dcc3d5679fb', a.id, a.name, coalesce(a.firm, 'Fusion Markets'), 'wd_hedge', 975.13, 'EUR',
       (now() at time zone 'UTC')::date, 'Trade #1158bc99 WD-Hedge · Finn + Pascal · ' || a.name, true
  from public.accounts a
 where a.id = '85b1b2a1-8bf1-4c09-8bb1-b3e9520b8896'
   and exists (select 1 from public.trade_plans p where p.id = '1158bc99-ef26-48c1-bab4-3e528029f927' and p.status = 'completed' and p.blown)
   and not exists (select 1 from public.transactions x where x.kind = 'wd_hedge' and x.auto_generated and x.notes like 'Trade #1158bc99 WD-Hedge%');

-- 5c) Konto ins Archiv des Besitzers (user_settings key 'archive' {konto_id: {archived, reason, at}}), nur wenn noch nicht archiviert
update public.user_settings
   set value = value || jsonb_build_object('6bdf9a8b-dbe7-41fd-a6fe-d907543a1b05',
                 jsonb_build_object('archived', true, 'reason', 'blown', 'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))),
       updated_at = now()
 where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'archive'
   and coalesce((value -> '6bdf9a8b-dbe7-41fd-a6fe-d907543a1b05' ->> 'archived')::boolean, false) = false
   and exists (select 1 from public.trade_plans p where p.id = '1158bc99-ef26-48c1-bab4-3e528029f927' and p.status = 'completed' and p.blown);

commit;

-- Kontrolle (alle 5 completed; 5 blown; genau 1 Buchung 975,13 € zu 1158bc99; Archiv-Eintrag reason blown):
-- select id, status, master_pl, slave_pl, blown, pl_quelle, completed_at from public.trade_plans
--  where id in ('e0c811c9-f135-4b28-9aa3-94172fb324a7','ae943cb2-6e99-412e-802a-bf821cc654db','7948da31-538c-4ec8-9a1a-a24d059b42f0',
--               '3256158c-196e-4c5e-b5cc-4d9b605e7e47','1158bc99-ef26-48c1-bab4-3e528029f927');
-- select amount, account_name, occurred_at, notes from public.transactions where kind = 'wd_hedge' and notes like 'Trade #1158bc99 WD-Hedge%';
-- select value -> '6bdf9a8b-dbe7-41fd-a6fe-d907543a1b05' from public.user_settings
--  where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'archive';

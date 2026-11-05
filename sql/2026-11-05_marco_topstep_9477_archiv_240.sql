-- Marco Topstep Express …49529477 (c640317f): zweiter Hand-Trade +240 € und danach archivieren
-- (Finn 05.11.2026 ~10:30 Dubai, Foto Accounts Marco → Topstep: „kannst du den archivieren und + 240 € machen").
-- Muster wie 2026-11-03_marco_topstep_8790_8246_archiv_200.sql: Master-P&L 0 (kein neuer Master-Trade belegt), die 240 € liegen auf der
-- Fusion-Seite → Hand-Plan completed + Buchung wd_hedge 240 € auf Fusion Slave; Archiv-Eintrag im archive-Blob der ID (reason blown).
-- Erster Hand-Trade vom 04.11. (Master −3.000 $, Fusion +500 €) bleibt unverändert. Einmalig über notes-Präfix.
with neu as (
  insert into public.trade_plans (user_id, master_account_id, master_name, master_firm, status, route, richtung, master_contracts, master_symbol, orbit_v3, hedge_eur, konto_typ, planned_for, started_at, ended_at, completed_at, master_pl, slave_pl, pl_quelle, hand_werte_at, blown, auto_plan, kapitel_id, notes, mt5_baseline)
  select '1c96cf0f-5aa6-46c6-8073-617e083e4378', 'c640317f-bb6a-45c4-8231-d5604f78dbb3'::uuid, '150k EXPRESS-V2-DLL-696284-49529477 → Funded', 'Topstep', 'completed', 'tsv2', 'sell', 3, 'NQZ6', true, 240, 'funded', '2026-11-05', now(), now(), now(), 0, 240, 'hand', now(), false, false, 2,
         'Hand-Trade Nova 2, von Hand +240 € (Finn 05.11.2026)',
         jsonb_build_object('hedge', jsonb_build_object('status', 'geschlossen', 'pl', 240, 'pl_offen', false, 'grund', 'hand', 'symbol', 'NAS100', 'waehrung', 'EUR', 'msg', 'von Hand, Betrag von Finn'))
   where not exists (select 1 from public.trade_plans p where p.master_account_id = 'c640317f-bb6a-45c4-8231-d5604f78dbb3' and p.notes like 'Hand-Trade Nova 2%')
  returning id
)
insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated, kapitel_id)
select '1c96cf0f-5aa6-46c6-8073-617e083e4378', 'bbfb1452-c95d-40a2-9492-f6ed0d62d953', 'Fusion Slave', 'Fusion Markets', 'wd_hedge', 240, 'EUR', '2026-11-05',
       'Trade #' || left(neu.id::text, 8) || ' WD-Hedge · Marco · Fusion Slave', true, 2
  from neu;

update public.user_settings
   set value = (value::jsonb
                || jsonb_build_object('c640317f-bb6a-45c4-8231-d5604f78dbb3', jsonb_build_object('at', now(), 'reason', 'blown', 'archived', true))),
       updated_at = now()
 where user_id = '1c96cf0f-5aa6-46c6-8073-617e083e4378' and key = 'archive';

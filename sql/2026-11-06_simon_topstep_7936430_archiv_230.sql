-- Simon Topstep Express …27936430 (19163697): zweiter Hand-Trade +230 € auf der Fusion-Seite, danach archivieren
-- (Finn 06.11.2026 ~04:45 Dubai, Foto Admin → Alle Accounts → Topstep Funded Futures: „kannst du den archivieren und + 230 eur machen“, Konto per Rückfrage: Simon).
-- Muster wie 2026-11-05_marco_topstep_9477_archiv_240.sql: Master-P&L 0 (kein neuer Master-Trade belegt), 230 € auf Fusion 488579 →
-- Hand-Plan completed + Buchung wd_hedge 230 € auf Simons Fusion-Konto; Archiv-Eintrag im archive-Blob der ID (reason blown).
-- Erster Hand-Trade vom 05.11. (8b6b1d0e, Master −2.700 $, Fusion +430 €) bleibt unverändert. Einmalig über notes-Präfix.
with vorlage as (
  select * from public.trade_plans where master_account_id = '19163697-d0a7-4a58-a18b-12649c2feb12' and notes like 'Hand-Trade, von Hand gegen gehedgt%' limit 1
), neu as (
  insert into public.trade_plans (user_id, master_account_id, master_name, master_firm, status, route, richtung, master_contracts, master_symbol, orbit_v3, hedge_eur, konto_typ, planned_for, started_at, ended_at, completed_at, master_pl, slave_pl, pl_quelle, hand_werte_at, blown, auto_plan, kapitel_id, notes, mt5_baseline)
  select v.user_id, v.master_account_id, v.master_name, 'Topstep', 'completed', 'tsv2', v.richtung, v.master_contracts, v.master_symbol, true, 230, 'funded', '2026-11-06', now(), now(), now(), 0, 230, 'hand', now(), false, false, 2,
         'Hand-Trade 2, von Hand +230 € Fusion (Finn 06.11.2026)',
         jsonb_build_object('hedge', jsonb_build_object('status', 'geschlossen', 'pl', 230, 'pl_offen', false, 'grund', 'hand', 'symbol', 'NAS100', 'waehrung', 'EUR', 'msg', 'von Hand, Betrag von Finn'))
    from vorlage v
   where not exists (select 1 from public.trade_plans p where p.master_account_id = '19163697-d0a7-4a58-a18b-12649c2feb12' and p.notes like 'Hand-Trade 2, von Hand +230%')
  returning id
)
insert into public.transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated, kapitel_id)
select '5409e926-09bc-4789-9c99-f8584d87a89a', '18d9b582-244e-4d3d-8de2-6501b23c98ef', '488579 → Live', 'Fusion Markets', 'wd_hedge', 230, 'EUR', '2026-11-06',
       'Trade #' || left(neu.id::text, 8) || ' WD-Hedge · Simon · 488579 → Live', true, 2
  from neu;

update public.user_settings
   set value = (value::jsonb
                || jsonb_build_object('19163697-d0a7-4a58-a18b-12649c2feb12', jsonb_build_object('at', now(), 'reason', 'blown', 'archived', true))),
       updated_at = now()
 where user_id = '5409e926-09bc-4789-9c99-f8584d87a89a' and key = 'archive'
   and coalesce(value->'19163697-d0a7-4a58-a18b-12649c2feb12'->>'archived', 'false') <> 'true';

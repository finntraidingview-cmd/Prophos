-- JACOB FUNDINGPIPS 100k …6924/…6925 GEBLOWT (26.10.2026, Finn: „ja“ — beide als geblowt archivieren, Trades vom 23.10. als blown).
-- …6924: Daily Loss gerissen am 23.10. (Tagesstart 96.463,40, Grenze 3 % = 2.893,90, Trade −2.990, Plan f9cdad00).
-- …6925: Max Overall Loss gerissen am 23.10. (Endstand 89.792,93 < Boden 90.000, Plan d09e6f53).
-- Ursache: Bulk-Vorlage „FundingPips 100k Phase 1“ trug Flex-Werte → Planer rechnete Flex (sql/2026-10-26_fundingpips_vorlage_standard.sql).
-- Wirkung wie der Blow-Takt (_konto_archiv_eintragen): Plan blown = true + mt5_baseline.final.konto_geblowt, Konto im Archiv des
-- Besitzers als 'blown', Echo-Löschauftrag für den verknüpften MT5-Login. Nur UUIDs. Wiederholbar (idempotent).

-- 1) Die zwei letzten Trades als blown markieren (beide schon completed)
update trade_plans
   set blown = true,
       mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
         jsonb_build_object('art', 'daily_loss', 'quelle', 'sql', 'text', 'FundingPips Max Daily Loss gerissen (3 % der Tagesstart-Equity)',
                            'at', now(), 'lesung', 'hand'), true),
       updated_at = now()
 where id = 'f9cdad00-50bd-48ff-a8d9-b404833bf547' and status = 'completed' and blown is not true;

update trade_plans
   set blown = true,
       mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
         jsonb_build_object('art', 'max_loss', 'quelle', 'sql', 'text', 'FundingPips Max Overall Loss gerissen (Endstand unter Boden 90.000)',
                            'balance', 89792.93, 'boden', 90000, 'at', now(), 'lesung', 'hand'), true),
       updated_at = now()
 where id = 'd09e6f53-5caa-44a4-93cc-dcd6233ad66b' and status = 'completed' and blown is not true;

-- 2) Beide Konten im Archiv des Besitzers als 'blown' (wie archiveAccount; schon archivierte bleiben unverändert)
update user_settings
   set value = coalesce(value, '{}'::jsonb)
             || case when coalesce((value -> '8c988e1e-24ec-4ddc-a461-bf5666cb9c77' ->> 'archived')::boolean, false) then '{}'::jsonb
                     else jsonb_build_object('8c988e1e-24ec-4ddc-a461-bf5666cb9c77', jsonb_build_object('archived', true, 'reason', 'blown',
                            'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))) end
             || case when coalesce((value -> 'c8b2d5b4-f2aa-4ebf-a954-223f609b0843' ->> 'archived')::boolean, false) then '{}'::jsonb
                     else jsonb_build_object('c8b2d5b4-f2aa-4ebf-a954-223f609b0843', jsonb_build_object('archived', true, 'reason', 'blown',
                            'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))) end,
       updated_at = now()
 where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and key = 'archive';

-- 3) Echo-Löschauftrag je verknüpftem MT5-Login (wie _konto_archiv_eintragen)
insert into echo_loesch_auftraege (mt5_login, grund, account_name, angelegt_am, erledigt_am, erledigt_info)
select l.mt5_login::text, 'blown', a.name, now(), null, null
  from mt5_links l join accounts a on a.id = l.account_id
 where l.account_id in ('8c988e1e-24ec-4ddc-a461-bf5666cb9c77', 'c8b2d5b4-f2aa-4ebf-a954-223f609b0843') and l.mt5_login is not null
on conflict (mt5_login) do update set grund = excluded.grund, account_name = excluded.account_name, angelegt_am = excluded.angelegt_am,
                                      erledigt_am = null, erledigt_info = null;

-- Kontrolle:
-- select left(id::text,8), status, blown, mt5_baseline->'final'->'konto_geblowt'->>'art' from trade_plans
--  where id in ('f9cdad00-50bd-48ff-a8d9-b404833bf547','d09e6f53-5caa-44a4-93cc-dcd6233ad66b');
-- select value->'8c988e1e-24ec-4ddc-a461-bf5666cb9c77', value->'c8b2d5b4-f2aa-4ebf-a954-223f609b0843' from user_settings
--  where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and key = 'archive';

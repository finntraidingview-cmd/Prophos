-- APEX GEBLOWT — zwei konkrete Pläne nachtragen (Finn 20.10.2026 ~05:00 Dubai, Radar „Abhaken · 13": „Diese beiden sind schon geblowt").
-- Befund S3: beide Apex-100k-Konten endeten bei 96.951,40 $ = 97.000 (100k − Max-DD 3.000) − 48,60 $ Gebühren → Apex' eigene
-- Liquidation; der Blow-Takt lief nicht (regeln.abhaken_auto aus seit 19.10.), Moritz' Endstand kam vom Reader (final.quelle demo).
-- NICHT automatisch eingespielt — Finn entscheidet. Wiederholbar (idempotent). Nur Plan-/Konto-UUIDs, keine Kontonummern.
-- Wirkung wie tsxGeblowtKonto im Tab: Plan blown = true + mt5_baseline.final.konto_geblowt, Konto im Archiv des Besitzers als 'blown'.

-- 1) Chris, Plan aea63796 (Orbit V2 SELL 3 NQ, zu 10:42 Dubai, Balance 96.951,40)
update trade_plans
   set blown = true,
       mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
         jsonb_build_object('art', 'apex_boden', 'quelle', 'sql', 'text', 'Balance 96.951 $ ≤ Boden 97.000 $ (100k − Max-DD 3.000 $)',
                            'balance', 96951.4, 'boden', 97000, 'at', now(), 'lesung', 'hand'), true)
 where id = 'aea63796-fe65-4a31-b29f-a9eb2845c999' and status = 'review' and blown is not true;

-- 2) Moritz, Plan 4da6b343 (Orbit V2 BUY 3 NQ, zu 09:57 Dubai, Balance 96.951,40)
update trade_plans
   set blown = true,
       mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
         jsonb_build_object('art', 'apex_boden', 'quelle', 'sql', 'text', 'Balance 96.951 $ ≤ Boden 97.000 $ (100k − Max-DD 3.000 $)',
                            'balance', 96951.4, 'boden', 97000, 'at', now(), 'lesung', 'hand'), true)
 where id = '4da6b343-6007-44d3-836e-98b646bc9730' and status = 'review' and blown is not true;

-- 3) Konten als geblowt archivieren (user_settings key 'archive' = {konto_id: {archived, reason, at}} — derselbe Eintrag wie archiveAccount)
update user_settings
   set value = coalesce(value, '{}'::jsonb) || jsonb_build_object('bdcfa3d2-14c3-4dc9-ad47-c11a4f93c073',
         jsonb_build_object('archived', true, 'reason', 'blown', 'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))),
       updated_at = now()
 where user_id = '7b1bc9a3-94d3-4603-a232-c10fc2df3262' and key = 'archive'
   and not coalesce((value -> 'bdcfa3d2-14c3-4dc9-ad47-c11a4f93c073' ->> 'archived')::boolean, false);

update user_settings
   set value = coalesce(value, '{}'::jsonb) || jsonb_build_object('477b2ef8-9f2a-4365-9e70-dbd5fe1d656d',
         jsonb_build_object('archived', true, 'reason', 'blown', 'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))),
       updated_at = now()
 where user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and key = 'archive'
   and not coalesce((value -> '477b2ef8-9f2a-4365-9e70-dbd5fe1d656d' ->> 'archived')::boolean, false);

-- Kontrolle:
-- select left(id::text,8), status, blown, mt5_baseline->'final'->'konto_geblowt' from trade_plans where id in ('aea63796-fe65-4a31-b29f-a9eb2845c999','4da6b343-6007-44d3-836e-98b646bc9730');

-- TopstepX Geblowt-Auge — Daten-Korrektur Mike (14.10.2026, Finn am Bild von Mikes TopstepX-Dropdown)
-- Vorfall 13.10.2026: …37040641 und …72341888 stehen in TopstepX als „(MAXIMUM_LOSS Violation)", Prophos sah es nicht
-- (Blow-Takt kennt nur Orbit V2/Echo V2 ohne Kette; die Endlesungen scheiterten 8× an der Meldung „You Hit Your Maximum
-- Loss Limit"). …17758280 wurde dagegen aus der Demo-Schätzung (−5.122 $) als geblowt abgehakt, lebt aber:
-- TopstepX BAL 147.123,54 $ > MLL 145.500 $, RP&L −2.876,46 $, kein Hinweis im Dropdown (Finn: „nicht geblowt, damit
-- richtig weiterrechnen"). Ab .1534 macht der PC-Tab das selbst (tsxGeblowtFolge); hier einmalig von Hand.
-- Eingespielt 14.10.2026 über Supabase MCP.

-- 1) …41 und …88 bei Mike als geblowt archivieren (user_settings key 'archive', wie archiveAccount() im Frontend)
update user_settings
   set value = value::jsonb
             || jsonb_build_object('9074c0c9-bfdf-4246-91f7-b63a8a8fd78b', jsonb_build_object('archived', true, 'reason', 'blown', 'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')))
             || jsonb_build_object('8c1ffaaa-b9ed-4bec-81ec-b9d0380ce983', jsonb_build_object('archived', true, 'reason', 'blown', 'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))),
       updated_at = now()
 where user_id = '32b854d1-866f-4e7e-ba0b-9bf63df2d993' and key = 'archive'
   and not ((value::jsonb) ? '9074c0c9-bfdf-4246-91f7-b63a8a8fd78b' and (value::jsonb) ? '8c1ffaaa-b9ed-4bec-81ec-b9d0380ce983');

-- 2) …88: letzter Trade (6c15a7bf, 13.10. 09:23–11:00 UTC, Lesung 8× an der Meldung gescheitert) → geblowt, Beweis am Plan
update trade_plans
   set blown = true,
       mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
                               jsonb_build_object('art', 'maximum_loss', 'quelle', 'dropdown_bild', 'text', 'MAXIMUM_LOSS Violation',
                                                  'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'lesung', 'hand_finn'), true),
       updated_at = now()
 where id::text like '6c15a7bf%' and master_account_id = '8c1ffaaa-b9ed-4bec-81ec-b9d0380ce983';

-- 3) …41: Plan 1bf18878 war schon blown — nur der Beweis dazu
update trade_plans
   set mt5_baseline = jsonb_set(coalesce(mt5_baseline, '{}'::jsonb), '{final,konto_geblowt}',
                               jsonb_build_object('art', 'maximum_loss', 'quelle', 'dropdown_bild', 'text', 'MAXIMUM_LOSS Violation',
                                                  'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'lesung', 'hand_finn'), true),
       updated_at = now()
 where id::text like '1bf18878%' and master_account_id = '9074c0c9-bfdf-4246-91f7-b63a8a8fd78b';

-- 4) …80: Plan 8245d11a lebt — blown zurück, echter P&L aus der TopstepX-Balance (152.298,66 → 147.123,54 = −5.175,12 $)
update trade_plans
   set blown = false,
       master_pl = -5175.12,
       pl_quelle = 'hand',
       mt5_baseline = (coalesce(mt5_baseline, '{}'::jsonb) #- '{final,puls_fehler}')
                      || jsonb_build_object('final', coalesce(mt5_baseline->'final', '{}'::jsonb)
                           || jsonb_build_object('balance_end', 147123.54, 'today_pnl', -2876.46, 'quelle', 'hand', 'plattform', 'tsx',
                                                 'balance_relativ', false, 'puls_fehler', null, 'puls_aufgegeben', false,
                                                 'hand_grund', 'Finn 14.10.2026 am TopstepX-Bild: BAL 147.123,54 > MLL 145.500, kein Dropdown-Hinweis — nicht geblowt')),
       updated_at = now()
 where id::text like '8245d11a%' and master_account_id = '35dd19f3-880c-4f18-88ad-808ca10da15a';

update accounts
   set tv_balance = 147123.54, tv_balance_at = now()
 where id = '35dd19f3-880c-4f18-88ad-808ca10da15a' and (tv_balance is null or tv_balance <> 147123.54);

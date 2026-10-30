-- MINDESTTAGE FTMO (Finn 30.10.2026: „Minimum Trading Days gibt's aktuell nur bei FundedNext, diese 5 Tage. Bei FTMO gibt's ab jetzt auch 4, in Phase 1 4
-- und in Phase 2 4. Auch für die bestehenden Accounts anwenden."). Neue Konten: prophos.html kontoMindesttage. Dieses Skript holt Vorlagen und Bestand nach.
-- Nicht eingespielt — der Master spielt ein, und Teil 3 erst auf Finns Wort.
-- ACHTUNG, DAS LÖST TRADES AUS: goal_kind schaltet im Auto-Planer „Tage sammeln" frei (app.py ap_konto_rechnen → ap_tage_mini). Fehlen Tage und der Bot
-- plant sonst nichts (Ziel erreicht, oder weniger als AP_REST_MIN_CFD Rest), kommt je Handelstag ein Mini-Vorschlag. FTMO plant in ganzen Lots (menge_schritt 1),
-- der Mini ist also 1 Lot, TP/SL 20–40 Pkt = 20–40 $, sofort wieder zu. Bei Konten mit ziel_erreicht_at hebt das auch die Sperre „Ziel erreicht" auf, deshalb Teil 3 extra.
-- Zählweise wie sql/2026-10-13_mindesttage_rueckwirkend.sql: goal_since = heute, alte Tage (Berlin-Tag von trade_plans.started_at, Konto als Master, jeder Status)
-- stehen als goal_done_offset fest. Nicht goal_since lösen: ap_tage_ist sieht nur Pläne der letzten 30 Tage, zielFortschritt alle — so bleibt der Stand überall gleich.
-- Grenze: ein Konto, dessen Phase IM SELBEN Eintrag umgestellt wurde, zählt die Tage der alten Phase mit — dann Offset von Hand (Badge „Tage x/4").
-- Grenze: Ein Konto schon über dem Ziel, das die Ziel-Wache erst nach dem Einspielen markiert, läuft durch Teil 2 und sammelt danach Tage mit Minis.
-- Nur Firma exakt FTMO (wie kontoMindesttage, nicht „FTMO Futures"), nur phase1/phase2, nur ohne goal_kind, nur nicht archiviert. Idempotent: beim zweiten Lauf ist goal_kind gesetzt.
-- Alle Gruppen: eine Firmenregel, auch Emins IDs, wie bei FundedNext.

-- 1) Schablonen
update bulk_vorlagen
   set goal_kind = 'trading_days', goal_target = 4
 where lower(trim(firm)) = 'ftmo' and account_type in ('phase1', 'phase2') and goal_kind is null;

-- 2) Bestand ohne Ziel-Markierung
update accounts a
   set goal_kind = 'trading_days', goal_target = 4, goal_manual = false, goal_since = date '2026-10-30',
       goal_done_offset = coalesce(a.goal_done_offset, 0) + (select count(distinct (p.started_at at time zone 'Europe/Berlin')::date)
                                                               from trade_plans p
                                                              where p.master_account_id = a.id and p.started_at is not null
                                                                and (p.started_at at time zone 'Europe/Berlin')::date < date '2026-10-30')
 where lower(trim(a.firm)) = 'ftmo' and a.account_type in ('phase1', 'phase2') and a.goal_kind is null
   and a.ziel_erreicht_at is null
   and not exists (select 1 from user_settings s where s.user_id = a.user_id and s.key = 'archive' and jsonb_typeof(s.value) = 'object' and s.value ? a.id::text);

-- 3) ERST NACH FINNS JA: Konten mit Ziel erreicht. Wer unter 4 Tagen liegt, wechselt von Review nach „Tage sammeln" und bekommt Mini-Vorschläge. Dasselbe Update
--    wie Teil 2, nur Bedingung ziel_erreicht_at gesetzt:
-- update accounts a
--    set goal_kind = 'trading_days', goal_target = 4, goal_manual = false, goal_since = date '2026-10-30',
--        goal_done_offset = coalesce(a.goal_done_offset, 0) + (select count(distinct (p.started_at at time zone 'Europe/Berlin')::date)
--                                                                from trade_plans p
--                                                               where p.master_account_id = a.id and p.started_at is not null
--                                                                 and (p.started_at at time zone 'Europe/Berlin')::date < date '2026-10-30')
--  where lower(trim(a.firm)) = 'ftmo' and a.account_type in ('phase1', 'phase2') and a.goal_kind is null
--    and a.ziel_erreicht_at is not null
--    and not exists (select 1 from user_settings s where s.user_id = a.user_id and s.key = 'archive' and jsonb_typeof(s.value) = 'object' and s.value ? a.id::text);

-- Kontrolle
-- select a.account_type, a.goal_kind, a.goal_target, a.goal_done_offset, count(*) from accounts a
--  where lower(trim(a.firm)) = 'ftmo' and a.account_type in ('phase1', 'phase2') group by 1, 2, 3, 4 order by 1, 2, 3, 4;

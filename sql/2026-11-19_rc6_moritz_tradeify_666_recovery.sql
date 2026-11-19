-- RC6 (Finn 19.11.2026 ~04:20 Dubai, EILIG — Trade soll HEUTE laufen): Moritz Tradeify 150k FTDFYSLX150431449666 → Winning Days (d2277e5f),
-- Tradeify-Dashboard „Total Profit Since Last Payout −5.415“. Prophos rechnet genau dasselbe: Anfrage 02.11. (pending_payouts received, tx b350a32c),
-- Zyklus-Start 161.443,84 (balance_start 03.11.-Trade fd43cf68), Live-Balance 156.028,14 (TV 15.11., frisch) → −5.415,70 $.
-- Seit 11.11. jeden Tag „Ziel schon voll“, kein Recovery: tradeify_zyklus_konto setzt bei Fehlbetrag > Max DD (4.500) gross → „von Hand planen“, aktiv False.
--
-- WEG (Slave RC6): derselbe Weg wie Mikes TR1 (2026-11-17_tr1_mike_tradeify_3058_recovery.sql, Schritt 2 = Tageszeile öffnen, PC-Tab würfelt 'recoverer').
-- Damit der Recoverer den Fall Minus > Max DD rechnet, nutzt der Code-Commit RC6 den VORHANDENEN Schalter je Konto accounts.wd_zyklus_regel ('an' = Recoverer
-- erzwingen, bisher nur Apex): bei Tradeify hebt 'an' nur die Max-DD-Grenze des Ausgleichs auf. Alles andere bleibt (Deckel bis zur WD-Liq 150.100, Frische,
-- RC5 „Trade läuft“, Sperre). Railway rechnet dann (Selbsttest tools/selftest_rc6_ausgleich_gross_hand.py mit den echten Zahlen):
--   TP = 5.415,70 + 1 $ + Puffer 30–60 (Saat Konto + CME-Tag, heute 40) → ≈ 5.457 $ · RC3-Staffel (> 2.000) → 1 NQ (= 273 Pkt; Liq 150.100 = 296 Pkt weg)
--   Hedge wie jeder Ausgleich: Staffel tradeify 110 € (Plus 6.028) ÷ normaler TP 273 = 402,93 €/1.000 $ → hedge_eur ≈ 2.199 € (Fusion-Gegenhedge)
--   Plan-Marke mt5_baseline.wd_ausgleich, ohne SL, Route tvv2 wie die WD-Pläne des Kontos.
-- Richtung BUY: Moritz hat heute keinen Futures-Trade; einziger Tradeify-Plan der ID ist Tradeify CFD 100k 122742 (buy, 06:08) → gleiche Richtung, kein
-- Gegenrichtungs-Riegel, egal ob die Firmen-Schlüssel gleich sind.
--
-- REIHENFOLGE
--   1. Schritt 1 einspielen (geht schon VOR dem Deploy: der alte Code liest wd_zyklus_regel bei Tradeify nicht).
--   2. Code-Commit RC6 (app.py tradeify_zyklus_konto) pushen → Railway-Deploy abwarten, bis er live ist.
--      Kontrolle: Admin → Payouts bzw. GET /wd-zyklus?ids=d2277e5f-4f07-4bf2-a981-e02ff3b97d96 → zyklus.aktiv true, grund „… Ausgleichs-Trade TP 5.457 $ (WD 5/5)
--      · über Max DD von Hand freigegeben · 1 NQ“, hedge_eur ≈ 2.199.
--   3. FRÜHESTENS 6 MIN NACH DEM LIVE-DEPLOY Schritt 2 einspielen (der PC-Tab hält den Zyklus-Stand bis 5 min, WD_ZYKLUS_ALTER_MS; mit dem alten Stand
--      setzt er wieder „Ziel schon voll“). Fällt die Zeile trotzdem zurück: Schritt 2 einfach nochmal.
--   4. Nach dem Trade (completed, nachgelesen): Schritt 3 (Schalter zurück auf null).

-- ── SCHRITT 1 (sofort) ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
begin;

update public.accounts set wd_zyklus_regel = 'an'
where id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and firm = 'Tradeify' and account_type = 'winning_days' and wd_zyklus_regel is null;

-- Handels-Würfel-Ausnahme nur für dieses Konto heute (TW4, wie TR1/2026-11-17_marc_7821_heute_rein.sql) — ein Pause-Wurf darf den Recovery nicht sperren
insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select 'aff98e60-e9a0-4821-9d1d-31634571a2f4', null, 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96', date '2026-11-19',
       'Master SQL RC6 (Finn 19.11.2026: Moritz Tradeify …9666 Recovery heute)'
where not exists (select 1 from public.planer_wuerfel_ausnahme
                   where konto_id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and tag = date '2026-11-19');

commit;

-- KONTROLLE nach Schritt 1:
-- select wd_zyklus_regel from accounts where id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96';                       -- 'an'
-- select * from planer_wuerfel_ausnahme where konto_id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and tag = '2026-11-19';   -- 1 Zeile


-- ── SCHRITT 2 (frühestens 6 min nach dem LIVE-Deploy des RC6-Codes) ────────────────────────────────────────────────────────────────────────────
-- Guard: nur Moritz' Zeile 19.11., nur wenn …9666 dort ohne Plan steht. Wie wd_payout_abgleich „heute wieder rein“: aktiv, Hinweis leer, eigene Startzeit
-- nach_start, Zeile 'leer' → 'geplant'; Würfel geleert → der PC-Tab würfelt selbst mit dem Railway-Stand (quelle 'recoverer', TP/Menge/Hedge aus dem Zyklus)
-- und legt nach 90 s Ruhe den Plan an. Startzeit: erste freie Minute ab jetzt + 10 min (Sekunden gestreut) mit ≥ 6 min Abstand zu jedem
-- geplanten/laufenden Start der ID (heute u. a. 06:08, 07:25:51, 08:28:31, 17:12:21), spätestens 16:15 Dubai (WD-Fenster bis 16:30).
with kand as (
  select now() + make_interval(mins => 10 + g, secs => floor(random() * 50)::int) t
  from generate_series(0, 660) g
),
frei as (
  select t from kand
  where t < timestamp '2026-11-19 16:15' at time zone 'Asia/Dubai'
    and not exists (select 1 from public.trade_plans p
                    where p.user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and p.status in ('planned', 'open') and p.start_um is not null
                      and abs(extract(epoch from (p.start_um - kand.t))) < 360)
  order by t limit 1
)
update public.wd_tagesplan w
set status = case when w.status in ('fertig', 'verpasst', 'leer') then 'geplant' else w.status end,
    konten = (select jsonb_agg(case when e.k->>'id' = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96'
                                    then (e.k - 'wuerfel' - 'naechster_lauf' - 'gruppe' - 'g_versatz_min' - 'g_gegen')
                                         || jsonb_build_object('aktiv', true, 'hinweis', '', 'farm', true, 'w_richtung', 'buy',
                                                               'nach_start', to_char(f.t at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                                               'rc6', 'Recovery per SQL 19.11.2026 (Finn: Zyklus −5.415,70 bei Tradeify)')
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)),
    updated_at = now()
from frei f
where w.tag = date '2026-11-19' and w.user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4'
  and exists (select 1 from jsonb_array_elements(w.konten) k
              where k->>'id' = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and coalesce(k->>'plan_id', '') = '')
returning w.status, (select to_char((k->>'nach_start')::timestamptz at time zone 'Asia/Dubai', 'HH24:MI:SS') from jsonb_array_elements(w.konten) k
                     where k->>'id' = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96') start_dubai;

-- KONTROLLE nach Schritt 2 (~2–3 min später: PC-Tab hat gewürfelt und nach 90 s Ruhe den Plan angelegt):
-- select k->>'aktiv' aktiv, k->>'hinweis' hinweis, k->'wuerfel' wuerfel, k->>'plan_id' plan_id, k->>'nach_start' nach_start, w.status
--   from wd_tagesplan w, jsonb_array_elements(w.konten) k
--  where w.tag = '2026-11-19' and w.user_id = 'aff98e60-e9a0-4821-9d1d-31634571a2f4' and k->>'id' = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96';
--   Erwartet: aktiv true, Hinweis leer, wuerfel {quelle recoverer, tp ≈ 5.447–5.477, instr nq}, plan_id gesetzt.
-- select left(id::text,8), status, route, richtung, master_tp, master_sl, master_contracts, master_symbol, hedge_eur, start_um at time zone 'Asia/Dubai',
--        mt5_baseline->>'wd_ausgleich' ausgleich
--   from trade_plans where master_account_id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and created_at > now() - interval '1 hour';
--   Erwartet: planned, tvv2, buy, TP ≈ 5.457, ohne SL, 1 × NQZ6, hedge_eur ≈ 2.199, wd_ausgleich true.


-- ── SCHRITT 3 (nach dem Trade: completed + nachgelesen) ─────────────────────────────────────────────────────────────────────────────────────────
-- Schalter zurück — sonst bliebe die Max-DD-Grenze für dieses Konto dauerhaft offen. Nach dem TP steht der Zyklus bei ≈ +41 $ → Payout anfragbar.
-- update public.accounts set wd_zyklus_regel = null where id = 'd2277e5f-4f07-4bf2-a981-e02ff3b97d96' and wd_zyklus_regel = 'an';

-- TR1 Teil A (Finn 17.11.2026 ~08:35 Dubai, Screenshot Tradeify-Dashboard): Mike Tradeify 150k …3058 (14e31eae) steht bei Tradeify auf
-- „Total Profit Since Last Payout −1.712,70 $“, Prophos zeigt aber „5/5 Winning Days ✓ · Payout anfragbar“ und der Farmer nahm das Konto heute
-- mit „Ziel schon voll“ raus. Finn: „anpassen, als Recovery-Trade markieren und heute noch so machen, dass wir morgen Payout anfragen können“.
--
-- URSACHE (Slave 15): Prophos kennt für …3058 nur die Payout-Buchung transactions 364da3aa vom 30.10. (Eingang), keine pending_payouts-Zeile. Der Zyklus
-- startet für Railway (wd_zyklus_stand / tradeify_zyklus_start_bal) deshalb erst nach dem 30.10.: Start-Balance = balance_start des 02.11.-Trades
-- 159.463,32 → Zyklus +257,70 $ → kein Ausgleich, „Payout anfragbar“.
-- Tradeify rechnet anders: Anfrage am 27.10. (nach dem 27.10.-Trade), 4.500 $ abgezogen zwischen dem 28.10.- und dem 29.10.-Trade
-- (28.10. balance_start 165.933,72 + 265,20 = 166.198,92; 29.10. balance_start 161.698,92 = −4.500). Zyklus-Start Tradeify = 165.933,72 − 4.500
-- = 161.433,72; 159.721,02 − 161.433,72 = −1.712,70 ✓ (Trading Days 12 = 28.10.–12.11., Winning Days 7 ✓).
--
-- WEG (ohne Deploy, über den BESTEHENDEN Tradeify-Ausgleich = Recovery, .2008/RC3/RC4/RC5):
--   Schritt 1: Payout-Anfrage als pending_payouts-Zeile nachtragen (received, mit der Buchung verknüpft → nicht doppelt gezählt).
--     requested_at = 28.10. (Tag des Abzugs), NICHT 27.10.: Prophos zählt Trades am Anfrage-Tag zum alten Zyklus und nimmt balance_start des ersten
--     Trades danach. Mit 27.10. wäre die Start-Balance 165.933,72 VOR dem Abzug → −6.212 $ > Max DD → „von Hand planen“, kein Ausgleich.
--     Mit 28.10. → Start 161.698,92 (29.10.-Trade), Zyklus −1.977,90 $. Das ist 265,20 $ strenger als Tradeify (der 28.10.-Trade +265,20 fehlt) —
--     sicher auf der richtigen Seite. Ausgleichs-TP (Railway tradeify_zyklus_konto) = 1.977,90 + 1 + Puffer 30–60 = 2.009–2.039 $ →
--     RC3-Staffel (> 2.000) = 1 NQ statt 7 MNQ. Nach dem TP: Prophos-Zyklus ≈ +31…+61 $, Tradeify ≈ +296…+326 $ → beide ≥ +1 $, Payout morgen frei.
--     Die Regel in Teil B rechnet den Zyklus künftig wie Tradeify (Abzug mitten im Zyklus) — dann passt auch der TP genau.
--   Schritt 1b: Handels-Würfel-Ausnahme nur für dieses Konto heute (TW4, wie 2026-11-17_marc_7821_heute_rein.sql) — ein Pause-Wurf darf den Recovery nicht sperren.
--   Schritt 2 (FRÜHESTENS 6 MIN NACH SCHRITT 1): Tageszeile von Mike wieder öffnen — wie Railways „Payout abgehakt → heute wieder rein“
--     (wd_payout_abgleich): Konto aktiv, Hinweis leer, eigene Startzeit nach_start, Zeile status geplant (stand „fertig“: Admin-Knöpfe „heute wieder
--     rein“ und 🎲 sind bei „fertig“ gesperrt). Würfel wird geleert → der PC-Tab/Farmer würfelt selbst mit dem Railway-Stand: wuerfel.quelle
--     'recoverer', TP/Menge aus dem Zyklus, Hedge = TP × Staffel-Satz (Fusion-Gegenhedge), Plan-Marke mt5_baseline.wd_ausgleich, ohne SL.
--     Warum 6 min Abstand: Der PC-Tab hält den Zyklus-Stand bis 5 min (WD_ZYKLUS_ALTER_MS). Sieht er die geöffnete Zeile noch mit dem alten Stand
--     (+257 $), setzt er wieder „Ziel schon voll“ und die Zeile fällt zurück auf „fertig“. Kein Klick von Finn nötig.
--   Richtung BUY: Mikes Tradeify …5297 lief heute BUY, Lucid …0002 läuft BUY → keine Gegenrichtung. Startzeit: erste freie Minute ab jetzt + 10 min
--   (Sekunden gestreut) mit ≥ 6 min Abstand zu jedem geplanten/laufenden Start der ID, spätestens 16:15 Dubai (Fenster bis 16:30).

-- ── SCHRITT 1 + 1b (sofort) ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
begin;

insert into public.pending_payouts (user_id, account_id, account_name, account_firm, amount, currency, requested_at, status, received_at, received_tx_id, notes)
select t.user_id, a.id, a.name, a.firm, t.amount, t.currency, date '2026-10-28', 'received', t.occurred_at::date, t.id,
       'TR1 17.11.2026 (Slave 15, Master-SQL): Anfrage nachgetragen. Tradeify: Anfrage 27.10., 4.500 $ abgezogen nach dem 28.10.-Trade; requested_at 28.10. = Abzugstag, damit der Zyklus-Start nach dem Abzug liegt'
from public.transactions t join public.accounts a on a.id = t.account_id
where t.id = '364da3aa-8962-4298-9f26-8003db2eec0a' and t.kind = 'payout' and a.id = '14e31eae-22e4-4684-8272-438a821a53cf'
  and not exists (select 1 from public.pending_payouts p where p.received_tx_id = t.id or (p.account_id = a.id and p.status in ('pending', 'received')));

insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select '32b854d1-866f-4e7e-ba0b-9bf63df2d993', null, '14e31eae-22e4-4684-8272-438a821a53cf', date '2026-11-17',
       'Master SQL TR1 (Finn 17.11.2026: Mike Tradeify …3058 Recovery heute)'
where not exists (select 1 from public.planer_wuerfel_ausnahme
                   where konto_id = '14e31eae-22e4-4684-8272-438a821a53cf' and tag = date '2026-11-17');

commit;

-- KONTROLLE nach Schritt 1 (1 Zeile, received, 28.10., tx verknüpft):
-- select requested_at, status, received_at, received_tx_id, amount, currency from pending_payouts where account_id = '14e31eae-22e4-4684-8272-438a821a53cf';
-- Sichtbar nach ≤ 5 min: Accounts/Admin → Payouts zeigt für …3058 nicht mehr „anfragbar“, sondern Zyklus −1.978 $ · Ausgleichs-Trade.


-- ── SCHRITT 2 (frühestens 6 min nach Schritt 1) ─────────────────────────────────────────────────────────────────────────────────────────────
-- Guard: nur die Zeile 17.11. von Mike, nur wenn …3058 dort ohne Plan steht; nichts anderes in der Zeile wird angefasst.
with kand as (
  select now() + make_interval(mins => 10 + g, secs => floor(random() * 50)::int) t
  from generate_series(0, 420) g
),
frei as (
  select t from kand
  where t < timestamp '2026-11-17 16:15' at time zone 'Asia/Dubai'
    and not exists (select 1 from public.trade_plans p
                    where p.user_id = '32b854d1-866f-4e7e-ba0b-9bf63df2d993' and p.status in ('planned', 'open') and p.start_um is not null
                      and abs(extract(epoch from (p.start_um - kand.t))) < 360)
  order by t limit 1
)
update public.wd_tagesplan w
set status = case when w.status in ('fertig', 'verpasst', 'leer') then 'geplant' else w.status end,
    konten = (select jsonb_agg(case when e.k->>'id' = '14e31eae-22e4-4684-8272-438a821a53cf'
                                    then (e.k - 'wuerfel' - 'naechster_lauf' - 'gruppe' - 'g_versatz_min' - 'g_gegen')
                                         || jsonb_build_object('aktiv', true, 'hinweis', '', 'farm', true, 'w_richtung', 'buy',
                                                               'nach_start', to_char(f.t at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                                                               'tr1', 'Recovery per SQL 17.11.2026 (Finn: Zyklus −1.712,70 bei Tradeify)')
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)),
    updated_at = now()
from frei f
where w.tag = date '2026-11-17' and w.user_id = '32b854d1-866f-4e7e-ba0b-9bf63df2d993'
  and exists (select 1 from jsonb_array_elements(w.konten) k
              where k->>'id' = '14e31eae-22e4-4684-8272-438a821a53cf' and coalesce(k->>'plan_id', '') = '')
returning w.status, (select to_char((k->>'nach_start')::timestamptz at time zone 'Asia/Dubai', 'HH24:MI:SS') from jsonb_array_elements(w.konten) k
                     where k->>'id' = '14e31eae-22e4-4684-8272-438a821a53cf') start_dubai;

-- KONTROLLE nach Schritt 2 (~2–3 min später: PC-Tab hat gewürfelt und nach 90 s Ruhe den Plan angelegt):
-- select k->>'aktiv' aktiv, k->>'hinweis' hinweis, k->'wuerfel' wuerfel, k->>'plan_id' plan_id, k->>'nach_start' nach_start, w.status
--   from wd_tagesplan w, jsonb_array_elements(w.konten) k
--  where w.tag = '2026-11-17' and w.user_id = '32b854d1-866f-4e7e-ba0b-9bf63df2d993' and k->>'id' = '14e31eae-22e4-4684-8272-438a821a53cf';
--   Erwartet: aktiv true, Hinweis leer, wuerfel {quelle recoverer, tp ≈ 2.009–2.039, kt 1, instr nq}, plan_id gesetzt.
-- select left(id::text,8), status, richtung, master_tp, master_sl, master_contracts, master_symbol, hedge_eur, start_um at time zone 'Asia/Dubai',
--        mt5_baseline->>'wd_ausgleich' ausgleich
--   from trade_plans where master_account_id = '14e31eae-22e4-4684-8272-438a821a53cf' and created_at > now() - interval '1 hour';
--   Erwartet: planned, buy, TP ≈ 2.009–2.039, ohne SL, 1 × NQZ6, hedge_eur > 0, wd_ausgleich true.
-- Fällt die Zeile zurück auf „Ziel schon voll“ (Tab hatte noch den alten Stand): Schritt 2 einfach nochmal einspielen.

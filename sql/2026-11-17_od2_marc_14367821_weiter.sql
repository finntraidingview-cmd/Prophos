-- OD2 (17.11.2026, Finn ~03:10 Dubai): FundedNext On Demand — Waiting for Payout erst, wenn AUCH die Consistency gegen den Netto-Profit erfüllt ist.
-- NICHT von Slaves einspielen — der Master spielt das nach dem Push des app.py-Fixes ein (execute_sql, DML).
--
-- Anlass: Marc, FundedNext 100k On Demand (accounts.id 27f94392…), am 16.11.2026 14:41 UTC vom Funded-CFD-Planer auf Waiting for Payout gestellt
-- (fcp_ziel.usd 2161 erreicht). FundedNext-Dashboard: Profit 2.226,83 $, Highest profit 1.960,56 $ = 88,04 % > 40 %, Required profit 4.901,40 $.
-- Der Planer rechnete die Consistency gegen die Summe der Gewinn-Tage (6.486,58 $ → 30 %), FundedNext gegen den Netto-Profit.
--
-- Nachgerechnet (Trades des Zyklus aus trade_plans, keine Payouts in pending/managed_payouts/transactions, Lesung tv_balance 17.11.):
--   27f94392 (Marc, 100k 14367821): −2.444,99 · +1.960,56 · +1.780,15 · −1.814,76 · +991,01 · +746,78 · +1.008,08 = +2.226,83
--            größter Tag 1.960,56 → 88,04 % · Wachstumsziel 2.161 erfüllt · On-Demand-Ziel = 1.960,56 ÷ 0,40 = 4.901,40 → NICHT bereit → zurück.
--   7fae7bdb (Ina, 100k 14351231): seit 30.10. 11:51 Waiting (damals Refund-Ziel 1. Zyklus, vor On Demand). Balance 100.356,22 → +356,22,
--            größter Tag +304,50 (30.10.) → 85,5 %. Wachstumsziel On Demand 2.000–2.250 $ NICHT erreicht → nach On-Demand-Regel NICHT bereit.
--   74afba19 (Ina, 100k 14350774): seit 30.10. 12:30 Waiting (ebenso). Balance 100.091,26 → +91,26, größter Tag +86,62 (27.10.) → 94,9 %.
--            Wachstumsziel NICHT erreicht → nach On-Demand-Regel NICHT bereit.
--   Die beiden Konten von Ina stehen also auch falsch, aber aus einem ANDEREN Grund (Waiting aus der Refund-Zeit vor On Demand, nicht die Consistency-
--   Basis). Ob dort ein Refund-Payout angefragt werden soll, entscheidet Finn — deshalb unten nur als Kommentar, nicht im Lauf.
--
-- ALLE 8 ON-DEMAND-KONTEN (Nachtrag 2, Finn ~03:15): Fall A = größter Tag > 40 % × Ziel → On-Demand-Ziel = größter Tag ÷ 0,40, jeder Tag ≤ 0,95 × größter Tag;
-- Fall B = größter Tag ≤ 40 % × Ziel → Ende genau aufs Ziel, jeder Tag ≤ 0,95 × 40 % × Ziel (auch Erholungstage). Profit = tv_balance − 100.000 (wie der
-- Planer), größter Tag = max Tages-P&L > 0 der beendeten Pläne seit Zyklusbeginn (Berlin-Tag), Ziel = fcp_ziel.usd des Zyklus (null → 2.000–2.250 gewürfelt).
--   Konto      Name/ID             Zyklus  Ziel   Profit      größter Tag  40 %×Ziel  Fall  On-Demand-Ziel  fehlt       Tagesdeckel
--   27f94392   Marc  …7821         1       2.161   +2.226,83   1.960,56     864,40     A     4.901,40        2.674,57    1.863  (Waiting seit 16.11. → zurück)
--   302d652e   Marc  …7823         2       2.190   −8.957,95   1.019,10     876,00     A     2.547,75       11.505,70      968
--   05daf6c6   (aff98e60) …3608    4       2.175     −385,07   1.573,71     870,00     A     3.934,28        4.319,35    1.495
--   320c26c6   (aff98e60) …0246    2       2.194   −3.536,98   1.899,85     877,60     A     4.749,63        8.286,61    1.805
--   373f1ba2   (aff98e60) …7427    2       2.226   −4.534,14   2.495,26     890,40     A     6.238,15       10.772,29    2.371
--   f7cb04cb   (fb42b5c3) …6734    1       2.223   +1.005,18      43,51     889,20     B     2.223,00        1.217,82      844
--   7fae7bdb   Ina   …1231         1       (null)    +356,22     304,50     ≥ 800      B     2.000–2.250   ≥ 1.643,78    ≥ 760  (Waiting seit 30.10., s. oben)
--   74afba19   Ina   …0774         1       (null)     +91,26      86,62     ≥ 800      B     2.000–2.250   ≥ 1.908,74    ≥ 760  (Waiting seit 30.10., s. oben)
--   Achtung Belege: bei 302d652e (Plan-Summe −6.890,55 ≠ Profit −8.957,95), 05daf6c6 (+1.580,06 ≠ −385,07) und f7cb04cb (+43,51 ≠ +1.005,18) decken die
--   Pläne den Profit nicht — Hand-Trades ohne Plan bzw. Zyklusbeginn-Balance ≠ 100k. Dort kann der echte größte Tag (Firmen-Dashboard) höher liegen;
--   der Planer sieht nur die Pläne. Fall A trifft also sofort 5 Konten (davon 4 tief im Minus: viele Tage ≤ Deckel nötig), Fall B 3 Konten.
--
-- REIHENFOLGE: erst den app.py-Fix (OD2) pushen und auf Railway live sehen, DANN diese Datei. Die Spalte accounts.fcp_wartet_zurueck (Merker des Knopfs
-- „zurück“, sql/2026-11-10_fcp_wartet_zurueck.sql) gibt es live nicht (17.11.2026 geprüft) — ohne Merker stellte ein alter Backend-Stand das Konto
-- nach 5 min wieder auf Waiting. Mit dem OD2-Fix plant der Planer weiter (On-Demand-Ziel 4.901 $ (Consistency)) und stellt erst bei ≥ 4.901,40 $ um.

-- Vorher ansehen:
select id, name, waiting_payout_since, fcp_ziel, tv_balance, payout_ready_at
from accounts
where id in ('27f94392-6d8d-4ccf-92a0-9edf5c008aad', '7fae7bdb-c483-4495-a01c-417316bbb351', '74afba19-5f97-4bd9-94f2-5660a67aba2f');

-- Marc …7821 aus Waiting for Payout zurück (nur wenn es noch das Waiting vom 16.11. ist):
update accounts
set waiting_payout_since = null
where id = '27f94392-6d8d-4ccf-92a0-9edf5c008aad'
  and account_type = 'funded_cfd'
  and on_demand is true
  and waiting_payout_since >= '2026-11-16 14:41:00+00' and waiting_payout_since < '2026-11-16 14:42:00+00'
returning id, name, waiting_payout_since;

-- NUR AUF FINNS WORT (Ina, Waiting aus der Refund-Zeit, Wachstumsziel nicht erreicht):
-- update accounts
-- set waiting_payout_since = null
-- where id in ('7fae7bdb-c483-4495-a01c-417316bbb351', '74afba19-5f97-4bd9-94f2-5660a67aba2f')
--   and account_type = 'funded_cfd' and on_demand is true and waiting_payout_since < '2026-10-31'
-- returning id, name, waiting_payout_since;

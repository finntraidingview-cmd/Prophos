-- ST1 (15.11.2026, Master mit Finns FundingPips-Regeln): Add-on „Striking“ für FundingPips Funded CFD.
-- Der Schalter wird von Hand je Konto gesetzt (Chip „Striking“ in der Spalte Add-ons, wie On Demand). Idempotent.
-- Ohne diese Spalte läuft alles wie bisher: fcp_planen, /konto-ziele und die Ziel-Wache fallen auf den alten Select zurück.
--
-- striking: Konto läuft im FundingPips-Striking-System. Die Regel steht im Code (FCP_STRIKING_STANDARD, FundingPips, Werte je 100k linear skaliert):
--   mindestens 7 Gewinntage je Zyklus mit je ≥ 500 $; zuerst nur Gewinntag-Trades (TP 550–750 $, SL 700–800 $), gesammelt wird auch über das Ziel hinaus;
--   danach Consistency 35 % (fcp_cons_finn); jeder Trade hat SL ≤ 1 % der Größe ÷ 1,15 (Nachzieh-Toleranz des Bots) × 0,95 (100k: 826 $, ST1b); kein Refund-Zyklus.
--   Je Firma überschreibbar in funded_cfd_plan_regeln.firmen[].striking = {gewinntage_anzahl, gewinntag_min_je_100k, consistency_pct,
--   tp_je_100k, sl_je_100k, verlust_max_pct} (false = keine Striking-Regel).
alter table public.accounts add column if not exists striking boolean not null default false;
comment on column public.accounts.striking is 'ST1 15.11.2026: Striking-Konto (FundingPips) — Funded-CFD-Planer nutzt die Striking-Regel der Firma (7 Gewinntage, Consistency 35 %, Verlust je Trade < 1 %)';

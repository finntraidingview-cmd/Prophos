-- O1 (05.11.2026, Finn ~07:20 Dubai): FundedNext On-Demand-Konten + festes Ziel je Funded-CFD-Konto.
-- „Auf den Account drücken und On Demand switchen; dann gelten diese Regeln" · „das Ziel wird je Account einmal per Zufall gewählt und steht fest".
-- Idempotent. Ohne diese Spalten läuft der Funded-CFD-Planer genau wie bisher (fcp_planen fällt auf den alten Select zurück).
--
-- on_demand: Konto ist ein On-Demand-Konto (Finn schaltet es im Konto-Bearbeiten). Regel im Code (FCP_ON_DEMAND_STANDARD, FundedNext:
--   Ziel 2.000–2.250 $ je 100k skaliert, Consistency 40 %, kein Refund-Trade, keine Gewinntage, Payout sofort anfragbar), je Firma
--   überschreibbar in funded_cfd_plan_regeln.firmen[].on_demand = {"ziel_je_100k": [von, bis], "consistency_pct": p}.
-- fcp_ziel: festes Ziel des laufenden Payout-Zyklus {"zyklus": n, "usd": Ziel über der Kontogröße, "at": ISO-Zeit}. Schreibt nur der Planer
--   (einmal je Zyklus gewürfelt); nach einem Payout (neuer Zyklus) oder wenn der Wert nicht mehr im Ziel-Bereich liegt, würfelt er neu.
alter table public.accounts add column if not exists on_demand boolean not null default false;
alter table public.accounts add column if not exists fcp_ziel jsonb;
comment on column public.accounts.on_demand is 'O1 05.11.2026: On-Demand-Konto (FundedNext) — Funded-CFD-Planer nutzt die On-Demand-Regel der Firma';
comment on column public.accounts.fcp_ziel is 'O1 05.11.2026: festes Ziel je Payout-Zyklus {zyklus, usd, at} — schreibt der Funded-CFD-Planer';

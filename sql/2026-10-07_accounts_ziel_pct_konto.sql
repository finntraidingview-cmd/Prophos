-- 2026-10-07 — Ziel-% je Konto (Finn, 07.10.2026): FundingPips-Konto …9722 läuft noch auf dem ALTEN FundingPips-Plan
-- (Phase 1 = 10 % Ziel, Phase 2 = 5 %), die Firmen-Regel in auto_plan_regeln hat seit den Kernwerten 8 % / 5 %. Die Ziel-Wache
-- (app.py zw_tick) rechnete deshalb 108.000 als Ziel, taggte das Konto bei 108.139 „🎯 bestanden → Phase 2" und sperrte den
-- Start — tatsächlich fehlen bei 10.000 Ziel noch ~1.860 $ (FundingPips-Dashboard: 81,4 %).
-- accounts.ziel_pct_konto = {"phase1": 10, "phase2": 5} überschreibt je Phase den ziel_pct der Firmen-Regel — nur an diesem
-- Konto; neue FundingPips-Konten bleiben bei der Regel (null). Ziel-Wache und Auto-Planer lesen die Spalte (ap_regel_konto).
-- Eingespielt 07.10.2026 (Master). Wiederholbar.
alter table accounts add column if not exists ziel_pct_konto jsonb;
comment on column accounts.ziel_pct_konto is 'Ziel-% je Phase nur für dieses Konto, z. B. {"phase1":10,"phase2":5}; null = Firmen-Regel (auto_plan_regeln). 07.10.2026';
update accounts
   set ziel_pct_konto = '{"phase1": 10, "phase2": 5}'::jsonb,
       ziel_erreicht_at = null, ziel_erreicht_bal = null, ziel_usd = null   -- Tag weg, die Ziel-Wache setzt ihn ggf. neu
 where id = '7bf177c3-6cb6-4231-afbd-60c8e3d7ce6a';

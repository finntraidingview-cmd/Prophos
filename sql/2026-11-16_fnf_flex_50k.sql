-- LF1b (Master 16.11.2026, Finn + FundedNext Help-Center „Flex FundedNext Account“): FundedNext Futures Flex 50k Funded als Profil im Funded-Planer Futures
-- (funded_plan_regeln id 1, Firma „FundedNext Futures“ — bis heute ohne Werte, an: false). Gilt für alle Unternehmen (Standard). Idempotent, ändert nur FNF Futures.
--
-- Firmenregeln Flex 50k Funded: Max Loss Limit 1.500 $ (EOD trailing, Lock bei 50.100 = Größe + 100 → lock_usd 100), KEIN Daily Loss, keine Consistency,
-- max 3 Mini / 30 Micro, Benchmark Day (Gewinntag) ab 200 $ (WD_GOOD_DAY_MIN im Code), 5 davon + ≥ 500 $ Zyklus-Gewinn für eine Auszahlung,
-- höchstens 50 % des Gewinns, max 1.500 $ je Payout, 95 % Anteil.
-- Finns Vorgaben: Ziel-Gewinn 6.000–8.000 $ (fest je Konto × Zyklus), EIN Pump-Trade aufs Ziel (pump2 mit pump2_pct 0 = nie Trade 2), 1–2 NQ,
-- SL 1.300–1.400 $ immer gesetzt (ohne DLL ist das MLL 1.500 die Grenze; der Code deckelt zusätzlich auf Abstand zur Liq − 50 $), Hedge 350 € auf 1.500 $,
-- danach Winning Days. Schalter je Größe: Firma an, nur 50k mit Werten (an: true) — andere FNF-Größen gelten damit als aus (fdp_groesse_an).

update public.funded_plan_regeln r
set firmen = (
  select jsonb_agg(
    case when f->>'name' = 'FundedNext Futures' then
      jsonb_set(
        f || '{"an": true, "tp_modus": "pump2", "symbol": "NQ", "lock_usd": 100}'::jsonb,
        '{je_groesse}',
        coalesce(f->'je_groesse', '{}'::jsonb) || jsonb_build_object('50000', coalesce(f->'je_groesse'->'50000', '{}'::jsonb) || '{
          "an": true,
          "dd": 1500,
          "ziel_gewinn": [6000, 8000],
          "ziel_toleranz_pct": 10,
          "pump2_pct": 0,
          "ein_kontrakte": {"1": 0.5, "2": 0.5},
          "ein_sl": [1300, 1400],
          "sl_kein_pct": 0,
          "sl_hinter_liq": false,
          "t1_von": "03:00",
          "t1_bis": "16:00",
          "hedge_eur": 350,
          "hedge_auf_usd": 1500
        }'::jsonb),
        true)
    else f end
    order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
),
updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.firmen) f where f->>'name' = 'FundedNext Futures');

-- FTMO IM FUNDED-CFD-PLANER (Finn 03.11.2026 ~01:10 Dubai: „das passt perfekt“). Neue Firma in funded_cfd_plan_regeln.firmen[], an = true.
-- Alles 1:1 wie FundedNext, nur Ziel und Lots weichen ab (FTMO US100.cash/NAS100 ≈ 1 $/Pkt je Lot laut firm_specs, FundedNext 10 $/Pkt):
--   100k: dd 10.000 · sl [1750, 2450] · sl_1pct [670, 780] · lots [10, 17.5] · ziel [1500, 2500] · hedge_eur 1500
--   200k: dd 20.000 · sl [3500, 4900] · sl_1pct [1500, 1700] · lots [10, 17.5] · ziel [1500, 2500] · hedge_eur 3000
--   erster_payout (Refund, Zyklus 1): ziel [50, 100], hedge_eur_je_dd 0,5 (100k 5.000 € auf 10.000 $, 200k 10.000 € auf 20.000 $); Lots nach
--   Verhältnis × 2 (app.py fcp_lots_verhaeltnis, c7e31fda/b0dd1eb3). Lot-Schritt 0,01 (FCP_LOT_SCHRITT). tp_deckel_plus 1000 wie FundedNext.
-- Schlüssel „ftmo“ (exakt nach _ap_norm): trifft accounts.firm 'FTMO' mit account_type funded_cfd, nie „FTMO Futures“ (Schlüssel ftmofutures).
-- Beispiele (Mitte 13,75 Lot, Ziel 2.000 $): normal TP ≈ 145 Pkt; Refund 50 $ → 0,68 Lot, 75 $ → 1,03, 100 $ → 1,37 (je ≈ 73 Pkt).
-- Idempotent: nur anhängen, wenn noch kein Eintrag mit namen ∋ 'ftmo' steht.
update public.funded_cfd_plan_regeln
   set firmen = firmen || '[
  {"name": "FTMO", "namen": ["ftmo"], "an": true, "tp_deckel_plus": 1000,
   "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5},
   "je_groesse": {"100000": {"ziel": [1500, 2500], "sl": [1750, 2450], "sl_1pct": [670, 780],   "lots": [10, 17.5], "hedge_eur": 1500, "dd": 10000},
                  "200000": {"ziel": [1500, 2500], "sl": [3500, 4900], "sl_1pct": [1500, 1700], "lots": [10, 17.5], "hedge_eur": 3000, "dd": 20000}}}
]'::jsonb,
       updated_at = now()
 where id = 1
   and not exists (select 1 from jsonb_array_elements(firmen) e where e->'namen' ? 'ftmo');

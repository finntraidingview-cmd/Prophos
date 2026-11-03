-- BLUE GUARDIAN IM FUNDED-CFD-PLANER (BG1, Finn 03.11.2026 ~23:59 Dubai, bestätigt; 2-Step Standard 100k Funded). Neue Firma in funded_cfd_plan_regeln.firmen[],
-- an = true. Code: app.py fcp_konto_rechnen (Phase A/B über je_groesse.gewinntage), fcp_gewinntage_ist (Zählung = ap_tage_ist wie die Gewinntage im
-- Challenge-Planer), fcp_zyklus_start (nur Trades nach dem letzten Payout).
--   Ziel je Payout-Zyklus [1000, 2000] $ Gewinn über der Kontogröße, je Trade gewürfelt; ab 1.000 → Ziel erreicht → „Waiting for Payout“ (wie die anderen).
--   Phase A: solange im Zyklus weniger als 3 Tage mit ≥ 500 $ (0,5 %) geschlossenem Gewinn → je Tag ein Trade, TP [550, 650] (auch über dem Ziel weiter,
--            ohne die 3 Tage zahlt Blue Guardian nicht aus). Phase B: Tage erfüllt, Ziel noch nicht → TP = Rest bis zum Ziel, ein Trade, kein Deckel.
--   SL [1250, 1600] $. Lots [1, 1.75] = dieselbe Formel wie FundedNext (Blue Guardian NAS100 10 $/Pkt je Lot wie FundedNext, firm_specs ppl 10; FTMO mit
--            1 $/Pkt hat dafür × 10). Gegenhedge 1.000 € auf 8.000 $ Max Drawdown (hedge_eur / dd, wie prophos.html tpFundedHedgeVorgabe).
--   Kein Refund: erster_payout false (kein kleines Ziel im 1. Zyklus). Zyklus 14 Tage: „Payout anfragbar ab“ setzt P1 beim Anlegen (Anlegetag + 14)
--            und bei jeder Anfrage (Anfrage-Datum + 14) — hier nichts.
-- Schlüssel „blueguardian“ (exakt nach _ap_norm, „Blue Guardian“); „bluegardian“ für den Tippfehler, den es in MT5-Ordnern gibt. Nur account_type funded_cfd.
-- Idempotent: nur anhängen, wenn noch kein Eintrag mit namen ∋ 'blueguardian' steht. Ausführen nur auf Finns Wort (Master).
update public.funded_cfd_plan_regeln
   set firmen = firmen || '[
  {"name": "Blue Guardian", "namen": ["blueguardian", "bluegardian"], "an": true, "erster_payout": false,
   "je_groesse": {"100000": {"ziel": [1000, 2000], "sl": [1250, 1600], "lots": [1, 1.75], "hedge_eur": 1000, "dd": 8000,
                             "gewinntage": {"anzahl": 3, "min": 500, "tp": [550, 650]}}}}
]'::jsonb,
       updated_at = now()
 where id = 1
   and not exists (select 1 from jsonb_array_elements(firmen) e where e->'namen' ? 'blueguardian');

-- Prüfen (nur lesen): Konten, die der Planer jetzt sieht
-- select a.name, a.firm, a.account_type, a.starting_balance, a.max_drawdown, a.waiting_payout_since from public.accounts a
--  where a.account_type = 'funded_cfd' and regexp_replace(lower(a.firm), '[^a-z0-9]', '', 'g') in ('blueguardian', 'bluegardian');

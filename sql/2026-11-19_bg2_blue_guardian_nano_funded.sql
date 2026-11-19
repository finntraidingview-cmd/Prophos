-- BG2 (Finn 19.11.2026 über den Master): Blue Guardian 2 Step NANO FUNDED 100k im Funded-CFD-Planer, neben Funded Standard.
-- Regeln: .claude/master/berichte/2026-11-19_BG1_blue_guardian_nano.md — Nano Funded: Consistency 50 % (bester Tag < 50 % des Zyklus-Gewinns, sperrt nur
-- den Payout), Cap 2 % = 2.000 $ je Zyklus, alle 14 Tage, keine Mindesttage, kein Guardian Shield, Daily 3 %, Max DD 10 % statisch.
--
-- KENNUNG wie im Challenge-Planer: accounts.max_drawdown ≥ 10 % der Kontogröße (Nano 10.000 / Standard 8.000) → app.py fcp_regel_konto (BG2-Commit):
-- flex.je_groesse ersetzt die Größen-Werte, flex.consistency_pct gilt für das Konto. Planer, Radar-Ziel/Boden (zw_funded_cfd), Konto-Seite (kz_rechnen)
-- und Reiter nehmen dieselbe Variante. Die beiden heutigen Funded-Konten (…608631, …617770) stehen auf 8.000 → bleiben Standard, bitgleich.
--
-- NANO FUNDED (Finn): 1:1 wie Funded Standard, außer
--   Ziel je Zyklus 800–1.200 $ (Finn „750/800 bis 1.200“, Master 800–1.200) — unter dem Cap 2.000 $.
--   Consistency 50 % je Zyklus über den vorhandenen Weg (fcp_consistency_pct → fcp_cons_finn, wie The5ers): TP aus dem Ziel abgeleitet, je Trade höchstens
--     50 % × (Summe der Gewinn-Tage + Rest) × 0,95 → bei 1.000 $ Ziel ≈ 2 × 475 $ + kleiner Rest; „Ziel erreicht“ erst, wenn auch der größte Tag ≤ 50 % ist.
--     Reset je Zyklus wie überall (nur Trades nach dem letzten Payout, fcp_zyklus_start).
--   SL 1.250–1.700 $ (Standard 1.250–1.600) · Lots 1–1,75 wie Standard · keine Gewinntage (Standard: 3 × 500).
--   Gegenhedge 500 € auf 10.000 $ Max Loss = 0,05 €/$ (Finn 19.11.2026; Standard 1.000 € / 8.000 $ = 0,125).
--   erster_payout false wie die Firma (kein Refund-Ziel).
-- ERST NACH DEM RAILWAY-DEPLOY DES BG2-CODES EINSPIELEN — das alte Backend kennt flex im Funded-CFD-Planer nicht und plante Nano-Funded als Standard
-- (Hedge 0,125 statt 0,05 €/$). Wiederholbar: setzt flex im blueguardian-Eintrag (ersetzt ein vorhandenes), alles andere bleibt. Nicht ohne Finns Wort (Master).

update public.funded_cfd_plan_regeln
   set firmen = (select jsonb_agg(case when e->'namen' ? 'blueguardian' then e || jsonb_build_object('flex', '{
          "name": "Nano",
          "ab_dd_pct": 10,
          "consistency_pct": 50,
          "je_groesse": {
            "100000": {"ziel": [800, 1200], "sl": [1250, 1700], "lots": [1, 1.75], "hedge_eur": 500, "dd": 10000}
          }
        }'::jsonb) else e end order by i)
                   from jsonb_array_elements(firmen) with ordinality t(e, i)),
       updated_at = now()
 where id = 1
   and exists (select 1 from jsonb_array_elements(firmen) e where e->'namen' ? 'blueguardian');

-- Prüfen (nur lesen):
-- select jsonb_pretty(e->'flex') from public.funded_cfd_plan_regeln, jsonb_array_elements(firmen) e where id = 1 and e->'namen' ? 'blueguardian';
-- select name, max_drawdown, case when max_drawdown >= 9999 then 'Nano' else 'Standard' end variante from public.accounts
--  where account_type = 'funded_cfd' and regexp_replace(lower(firm), '[^a-z0-9]', '', 'g') in ('blueguardian', 'bluegardian');

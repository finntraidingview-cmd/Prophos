-- BG1 (Finn 19.11.2026): Blue Guardian 2 Step NANO 100K (CFD) neben dem bisherigen 2 Step Standard im Auto-Planer.
-- Regeln + Quellen: .claude/master/berichte/2026-11-19_BG1_blue_guardian_nano.md (Help Center help.blueguardian.com, Stand 13./17.11.2026).
--   Nano 100K: Kauf 167 $ (≈ 145 €), Ziel P1 8 % / P2 5 %, Daily Loss 3 % (17:00 NY, höher aus Balance/Equity), Max DD 10 % STATISCH
--   (Boden 90.000), keine Mindesttage, keine Consistency in der Challenge. Standard bleibt wie er ist (8/4 %, Daily 4 %, DD 8 %, 3 Gewinntage).
--
-- KENNUNG AM KONTO = accounts.max_drawdown (kein neues Feld, kein Namens-Parser):
--   Nano 10.000 (10 %) · Standard 8.000 (8 %). Erkannt über den vorhandenen Varianten-Weg regel.flex (app.py ap_konto_flex / ap_regel_flex,
--   gebaut für FundingPips Flex): ab_dd_pct 10 → Max DD ≥ 10 % der Anfangsgröße = Nano-Werte aus flex.je_groesse, sonst Standard-Werte.
--   Planer (ap_konto_rechnen), Ziel-Wache (zw_ziel), Boden/Radar und Probelauf gehen alle über ap_regel_konto → dieselbe Variante.
--   Alle 6 heutigen BG-Konten stehen auf max_drawdown 8.000 → bleiben Standard, bitgleich.
--   Eigene Firma „Blue Guardian Nano“ verworfen: eigener Firmen-Schlüssel trennt den Gegenrichtungs-Riegel/Firmen-Abstand zwischen Nano und
--   Standard (Blue Guardian verbietet Hedging über Konten), und firm_specs/Preset (NAS100 10 $/Pkt) fehlten für den neuen Namen.
--   ⚠️ NANO-KONTO IMMER MIT MAX DD 10.000 ANLEGEN. Leer gelassen setzt DD1 (konto_dd_ergaenzen) den Firmen-Kernwert 8.000 → Standard-Plan
--      (SL bis 3.150 > Nano-Daily 3.000). Nachfolger Phase 2/Funded und Reset erben den Wert. goal_kind am Nano-Konto LEER lassen (keine Mindesttage).
--
-- NANO-WERTE (TP/Lots/Puffer = Standard-Werte von Finn; SL VORSCHLAG Slave, wegen Daily 3 %):
--   P1 TP 4.950–5.850 (2 Trades bis 8.000) · P2 TP 2.700–3.150 (2 Trades bis 5.000) · SL 2.000–2.500 (Standard 2.700–3.150 läge über/an
--   der Tagesgrenze 3.000) · Lots 4–5,3 · Puffer 25–50 · Boden 10 %.
--   daily_pct 3 → ap_tagesgrenze kappt den SL zusätzlich auf (3 % der Balance − heute realisierter Verlust − 100 $ Puffer) und gibt
--   tages_grenze_usd an den Plan (Echo V2 zieht den SL am Fill nach). gewinntage null: der Gewinntag-Weg der Firma gilt nie für Nano.
--   name „Nano“ (Teil C): nur die Reiter im Kernwerte-Editor (E3) — „Standard 100k“ / „Nano 100k“ statt „100k“ / „Flex 100k“; der Planer liest es nicht.
--   SL 2.000–2.500 (Finn 19.11.2026, neu statt 2.300–2.600: „das Daily von 3.000 nie treffen“) und Kauf 145 € von Finn bestätigt (über den Master).
--   Finns Bedingung geprüft: kein festes Max Loss / Max Risiko pro Trade für Nano — 2-step-nano-rules (Stop Loss nicht Pflicht, nur Daily 3 % +
--   DD 10 %), prohibited-trading-strategies (nur 80-%-Margin-Regel), AGB „Prohibited Strategies“ (nur „excessive risk … single trade“ ohne Zahl, Ermessen).
--   kauf_eur 145 (167 $): nur für den Kontowert = Echo-Hedge-Satz. Braucht den Code-Commit „BG1 Kontowert-Variante“ (ap_kw_regel_konto):
--   ohne ihn rechnet der Fusion-Hedge Nano mit Standard 300 € / 8 % (≈ 2,6–2,9× zu viel Hedge). ERST NACH DEM RAILWAY-DEPLOY EINSPIELEN.
--
-- Wiederholbar: setzt flex im blueguardian-Eintrag (ersetzt ein vorhandenes flex), alles andere bleibt. Nicht einspielen ohne Finns Wort (Master).

update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}',
       (select jsonb_agg(case when f->'namen' ? 'blueguardian' then f || jsonb_build_object('flex', '{
          "name": "Nano",
          "ab_dd_pct": 10,
          "dd_pct": 10,
          "kauf_eur": {"100000": 145},
          "je_groesse": {
            "100000": {
              "dd_pct": 10,
              "ziel_pct": {"phase1": 8, "phase2": 5},
              "daily_pct": 3,
              "gewinntage": null,
              "phasen": {
                "phase1": {"sl": [2000, 2500], "tp": [4950, 5850], "menge": [4, 5.3], "menge_schritt": 0.1,
                           "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10},
                "phase2": {"sl": [2000, 2500], "tp": [2700, 3150], "menge": [4, 5.3], "menge_schritt": 0.1,
                           "puffer": [25, 50], "ziel_pct": 5, "boden_pct": 10}
              }
            }
          }
        }'::jsonb) else f end order by i)
          from jsonb_array_elements(regeln->'firmen') with ordinality t(f, i))),
       updated_at = now()
 where id = 1
   and exists (select 1 from jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'blueguardian');

-- Prüfen (nur lesen):
-- select jsonb_pretty(f->'flex') from public.auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'blueguardian';
-- BG-Konten und welche Variante sie bekommen (Nano = max_drawdown ≥ 10 % der Größe):
-- select name, account_type, max_drawdown, goal_kind,
--        case when max_drawdown >= 0.10 * coalesce(starting_balance, account_size, 100000) - 1 then 'Nano' else 'Standard' end variante
--   from public.accounts where regexp_replace(lower(firm), '[^a-z0-9]', '', 'g') in ('blueguardian', 'bluegardian') order by created_at desc;

-- ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
-- TEIL 2 (BG2, NICHT AKTIV — braucht Code): Funded-CFD-Planer für Nano-Funded.
-- funded_cfd_plan_regeln kennt heute keine Variante je Konto (nur on_demand/striking-Schalter). Ein Nano-Funded liefe mit den
-- Standard-Werten: Ziel 1.000–2.000 (≤ Cap 2.000 ✓), SL 1.250–1.600 (< Daily 3.000 ✓), 3 Gewinntage × 500 (bei Nano unnötig, schadet nicht),
-- Consistency 50 % nur zufällig eingehalten, Gegenhedge 1.000 € / 8.000 $ = 0,125 €/$ — Nano-Funded ist ~390 € wert (145 × 1,8 × 1,5) → ≈ 3×.
-- Vorschlag nach Code (flex wie im Challenge-Planer, ab_dd_pct 10), Hedge-Satz offen für Finn:
--   "flex": {"ab_dd_pct": 10, "consistency_pct": 50,
--            "je_groesse": {"100000": {"ziel": [800, 1200], "sl": [1250, 1600], "lots": [1, 1.75], "hedge_eur": <Finn, z. B. 400>, "dd": 10000}}}
--   Ziel 800–1.200 $ je Zyklus (Finn 19.11.2026 „750/800 bis 1.200“, Master: 800–1.200 bis Finn anders sagt) — unter dem Cap 2.000 $ und mit
--   Consistency 50 % in mindestens 2 Gewinntagen; keine gewinntage-Regel; Zyklus 14 Tage wie Standard.

-- Auto-Planer + Kontowert: neue Firma „FundedNext Futures" (Finn 06./07.10.2026). Futures über Tradovate, Weg Orbit V2
-- (route tvv2) wie Tradeify. Schlüssel nach Normalisierung: _firm_norm → „FundedNext Futures", _ap_norm → „fundednextfutures"
-- (exakter Vergleich in ap_regel_finden — NICHT „fundednext", das ist die CFD-Firma mit eigenem Eintrag).
-- Finns Werte: 150k, Kauf 258 € je Konto, Max Drawdown 4.000 $, Ziel +8.000 $ (ziel_pct = 8.000 ÷ 150.000 × 100),
-- Consistency wie Tradeify: größter Tag höchstens 40 % des Ziels = 3.200 $ → Etappen 3.200 / 3.200 / 1.600.
-- Drawdown End-of-Day nachziehend, aber der Boden steigt NIE über die Startgröße (lock_bei_start, wie Apex Funded):
-- 146.000 → nach +3.200 149.200 → nach +3.200 150.000 fest. Gelesen von ap_kw_param/ap_kontowert (Kontowert: je Etappe
-- × (1 + Gewinn ÷ Polster), ab dem Lock statisch), ap_konto_rechnen (Boden) und vorrat_stufen_aus_kernwerten (Chance).
-- Planer-Phase analog Tradeify (3.450–3.550 unter Deckel 3.600) → 3.050–3.150 unter Deckel 3.200, Menge/Puffer gleich (NQ).
-- KEIN Vorrats-Ziel (Finn: FundedNext Futures ohne Ziel) — nur die Kernwerte.
-- Wiederholbar: ein vorhandener fundednextfutures-Eintrag wird ersetzt, nie doppelt angehängt; andere Firmen unverändert.
update auto_plan_regeln set regeln = jsonb_set(regeln, '{firmen}', (
  select coalesce(jsonb_agg(f order by ord) filter (where not (f->'namen' ? 'fundednextfutures')), '[]'::jsonb)
  from jsonb_array_elements(regeln->'firmen') with ordinality as x(f, ord)
) || '[{"namen": ["fundednextfutures"], "route": "tvv2", "symbol": "NQ", "groessen": [150000],
        "kauf_eur": 258, "dd_usd": 4000, "boden": "nachziehend", "lock_bei_start": true,
        "ziel_pct": {"challenge": 5.333333333333334},
        "phasen": {"challenge": {"ziel_pct": 5.333333333333334, "dd_usd": 4000, "tp": [3050, 3150], "tp_max": 3200, "sl": null,
                                 "menge": [2, 3], "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}]'::jsonb),
  updated_at = now()
where id = 1;

-- Kontrolle: genau ein Eintrag, Kernwerte wie oben
-- select f from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'fundednextfutures';

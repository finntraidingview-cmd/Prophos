-- Apex Funded/PA: Daily-Loss-Stufen für 100k (neu) und 150k (vervollständigt) — Finn 21.10.2026:
-- „Trag die Tabelle für 100K und 150K Daily Loss Limit ein, damit wir im Reiter immer die Liquidations reinkriegen."
-- Quelle: Apex Help Center „Scaling Levels (PA) Explained" + „Daily Loss Limit Explained" (Stand 15.04.2026), gelesen 21.10.2026.
-- Stufe = Schlussbalance der Vorsitzung (16:59:59 ET) → passt zu liq_aus_regel art 'stufen' (Stufe nach Tagesstart-Balance).
-- Fällt die Balance, fällt auch die Stufe (nie unter Stufe 1). Winning Days greifen über Zeile id 6 (wie funded) automatisch mit.
-- Vorher: Apex 100k fand KEINE Zeile (id 4 hat groesse 150000) → Radar zeigte nur den Konto-Boden 97.000, kein Daily Loss.

-- 150k: offizielle Stufe 3 (ab 153.000, 7 Minis) fehlte — Daily Loss dort unverändert 2.500, nur die Kontraktzahl stimmt jetzt.
update public.liq_regeln
set stufen = '[
  {"ab_balance":150000,"daily_loss_usd":2500,"minis":4,"micros":40},
  {"ab_balance":152000,"daily_loss_usd":2500,"minis":5,"micros":50},
  {"ab_balance":153000,"daily_loss_usd":2500,"minis":7,"micros":70},
  {"ab_balance":155000,"daily_loss_usd":3000,"minis":10,"micros":100},
  {"ab_balance":160000,"daily_loss_usd":4000,"minis":10,"micros":100}
]'::jsonb,
    notiz = 'Apex PA 150k, Stufen laut Apex Help Center (Scaling Levels PA, 15.04.2026): ab 150.000 DLL 2.500 (4 Minis) · ab 152.000 2.500 (5) · ab 153.000 2.500 (7) · ab 155.000 3.000 (10) · ab 160.000 4.000 (10, Max). Stufe nach Schlussbalance der Vorsitzung (= Tagesstart), fällt mit der Balance, nie unter Stufe 1. Erste Fassung 30.09.2026 aus Finns Screenshots (ohne Stufe 153.000).',
    quelle = 'Finn 30.09.2026 (Screenshots) + Apex Help Center, ergänzt 21.10.2026',
    updated_at = now()
where id = 4;

insert into public.liq_regeln (firma, kontotyp, groesse, art, stufen, notiz, quelle, maxdd_art, maxdd_lock_ueber_groesse_usd, updated_at)
select 'Apex Trader', 'funded', 100000, 'stufen', '[
  {"ab_balance":100000,"daily_loss_usd":1750,"minis":3,"micros":30},
  {"ab_balance":102000,"daily_loss_usd":1750,"minis":4,"micros":40},
  {"ab_balance":103000,"daily_loss_usd":1750,"minis":5,"micros":50},
  {"ab_balance":105000,"daily_loss_usd":2500,"minis":6,"micros":60},
  {"ab_balance":110000,"daily_loss_usd":3500,"minis":6,"micros":60}
]'::jsonb,
  'Apex PA 100k, Stufen laut Apex Help Center (Scaling Levels PA, 15.04.2026): ab 100.000 DLL 1.750 (3 Minis) · ab 102.000 1.750 (4) · ab 103.000 1.750 (5) · ab 105.000 2.500 (6) · ab 110.000 3.500 (6, Max). Stufe nach Schlussbalance der Vorsitzung (= Tagesstart), fällt mit der Balance, nie unter Stufe 1. Konto-Boden bleibt 97.000 (Finn 20.10.2026).',
  'Finn 21.10.2026 + Apex Help Center', 'eod_trailing', 100, now()
where not exists (select 1 from public.liq_regeln where firma = 'Apex Trader' and kontotyp = 'funded' and groesse = 100000);

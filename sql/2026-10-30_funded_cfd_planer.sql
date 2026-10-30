-- FUNDED-CFD-PLANER (30.10.2026, Finn ~07:00 Dubai: „Ja, bauen"). Regeln + Schalter des Planers für Funded-CFD-Konten (app.py fcp_*):
-- The5ers, FundedNext, FundingPips Standard, Tradeify CFD (Nachtrag Master 30.10.2026, nur 100k) — 1 Trade je Konto und Tag, Echo mit Fusion-Gegenhedge (route mt5, Slave = echo_hedge_account
-- der ID), als VORSCHLAG ohne Startzeit; Finn bestätigt von Hand (Admin → Funded Planer → CFD). Eigene Tabelle, damit der Funded-Planer
-- (funded_plan_regeln, Apex) und der Challenge-Planer (auto_plan_regeln) unberührt bleiben. Werte: Finns Diktat
-- (.claude/master/funded-cfd-planer-regeln.md, 30.10.2026 05:10–06:55 Dubai).
-- aktiv = false (Start AUS, bis Finn freigibt). Wieder an: update funded_cfd_plan_regeln set aktiv = true where id = 1;
-- Idempotent: create if not exists + on conflict do nothing (eine spätere Wertänderung = eigene Datei mit update).

-- firmen[]: name, namen = Firmenname nach _ap_norm (klein, nur a–z0–9; exakter Vergleich — „tradeifycfd" trifft nie Tradeify-Futures
-- „tradeify", die als funded/winning_days ohnehin nicht funded_cfd sind), an, ohne_namen = Teilwörter im Kontonamen, die nicht geplant werden
-- (FundingPips Flex kommt später). je_groesse (Kontogröße in $):
--   ziel [von, bis]   = Gewinn über der Kontogröße (Starting Balance), ab „von" → Ziel erreicht (Waiting for Payout); je Trade gewürfelt
--   tp_erster         = nur The5ers: fester TP im 1. Payout-Zyklus (kein Payout in der Historie) — 2 × 750 bis zum Ziel (Consistency 50 %)
--   sl [von, bis]     = Stop-Loss in $, gewürfelt; sl_1pct [von, bis] = Konten mit 1-%-Risk-Limit (accounts.max_risiko_trade gesetzt)
--   lots [von, bis]   = Master-Lots, gewürfelt (2 Nachkommastellen)
--   daily_loss        = nur zur Anzeige (Tradeify CFD 3.000 $; SL bleibt darunter) — keine Regel-Prüfung
--   hedge_eur, dd     = Fusion-Hedge: hedge_eur € auf dd $ Drawdown (Risiko Slave / Risiko Master, wie das Echo-Popup)
-- TP sonst = Ziel − bisheriger Gewinn (auch nach einem Verlusttag wieder genau aufs Ziel).
-- zeiten: firma_abstand_min (Starts derselben Firma je Gruppe), abstand_id_min (Starts derselben ID, ein PC), vorlauf_min. Das Startfenster
-- ist das des Challenge-Planers (auto_plan_regeln.zeiten).
-- auto_bestaetigen = false: Vorschläge ohne start_um (Testphase alles von Hand, Finn 29.10.2026). ziel_auto_wartet = false: Ziel erreicht
-- wird nur angezeigt („→ Waiting for Payout" im Konto), nicht selbst umgestellt.
create table if not exists public.funded_cfd_plan_regeln (
  id smallint primary key default 1 check (id = 1),
  aktiv boolean not null default false,
  auto_bestaetigen boolean not null default false,
  ziel_auto_wartet boolean not null default false,
  user_ids uuid[] not null default '{}',
  firmen jsonb not null default '[]'::jsonb,
  zeiten jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.funded_cfd_plan_regeln enable row level security;
-- Keine Policy: nur Railway (Service-Key) liest und schreibt, wie funded_plan_regeln.

insert into public.funded_cfd_plan_regeln (id, aktiv, auto_bestaetigen, ziel_auto_wartet, user_ids, firmen, zeiten) values (1, false, false, false,
  -- IDs der Gruppen „Hermann Technologies“ und „Emin“ (Master 30.10.2026: beide, Sicht je Gruppe getrennt), ohne die archivierte ID „Finn“
  -- (= wd_farmer_regeln.ids_aus ohne die Mitglieder der Emin-Gruppe — Emin steht dort nur für den WD-Farmer)
  coalesce((select array_agg(distinct m.user_id) from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
            where g.name in ('Hermann Technologies', 'Emin')
              and m.user_id::text not in (
                select x from public.wd_farmer_regeln w, jsonb_array_elements_text(coalesce(to_jsonb(w.ids_aus), '[]'::jsonb)) x
                 where w.id = 1
                   and x not in (select m2.user_id::text from public.id_gruppe_mitglied m2 join public.id_gruppen g2 on g2.id = m2.gruppe_id
                                  where g2.name = 'Emin'))), '{}'),
'[
  {"name": "The5%ers", "namen": ["the5ers"], "an": true,
   "je_groesse": {"100000": {"ziel": [1300, 1500], "tp_erster": 750, "sl": [1800, 2400], "lots": [14, 23], "hedge_eur": 750, "dd": 10000},
                  "200000": {"ziel": [1300, 1500], "tp_erster": 750, "sl": [3600, 5000], "lots": [15, 24], "hedge_eur": 1500, "dd": 20000}}},
  {"name": "FundedNext", "namen": ["fundednext"], "an": true,
   "je_groesse": {"50000":  {"ziel": [1500, 1850], "sl": [875, 1225],  "sl_1pct": [300, 400],   "lots": [1, 1.75], "hedge_eur": 750,  "dd": 5000},
                  "100000": {"ziel": [1500, 1850], "sl": [1750, 2450], "sl_1pct": [670, 780],   "lots": [1, 1.75], "hedge_eur": 1500, "dd": 10000},
                  "200000": {"ziel": [1500, 1850], "sl": [3500, 4900], "sl_1pct": [1500, 1700], "lots": [1, 1.75], "hedge_eur": 3000, "dd": 20000}}},
  {"name": "FundingPips", "namen": ["fundingpips"], "an": true, "ohne_namen": ["flex"],
   "je_groesse": {"50000":  {"ziel": [625, 1000],  "sl": [650, 800],   "lots": [0.375, 0.4], "hedge_eur": 1000, "dd": 5000},
                  "100000": {"ziel": [1250, 2000], "sl": [1300, 1600], "lots": [0.75, 0.8],  "hedge_eur": 2000, "dd": 10000}}},
  {"name": "Tradeify CFD", "namen": ["tradeifycfd"], "an": true,
   "je_groesse": {"100000": {"ziel": [1500, 2500], "sl": [1750, 2400], "lots": [2.5, 3.1], "hedge_eur": 2000, "dd": 10000, "daily_loss": 3000}}}
]'::jsonb,
'{"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}'::jsonb)
on conflict (id) do nothing;

-- Lauf-Protokoll: auto_plan_lauf mit quelle = 'funded_cfd' (nur Läufe mit neuen Vorschlägen). Keine Änderung an Triggern nötig:
-- trade_plans_kontoart_weg lässt funded_cfd auf route mt5 (mit Hedge) durch; Gegenrichtung und Firmen-Abstand prüft die DB wie immer beim Claim.

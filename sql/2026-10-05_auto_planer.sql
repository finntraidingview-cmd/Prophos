-- AUTO-PLANER (05.10.2026, Finn: „eine kleine KI, die erkennt, bei welchem Step der Account gerade steht, und automatisch den
-- nächsten Trade plant — ich gehe nur noch hin und drücke Bestätigen"). Stufe 1: nur Challenge/Phase 1/Phase 2, immer ohne
-- Hedge (Futures = Orbit V2 tvv2, CFD = Echo V2 mt5v2), Test nur bei zwei IDs. Der Planer (app.py, ap_*) legt Pläne mit
-- Startzeit an; ein Auto-Plan startet erst, wenn er bestätigt ist (auto_bestaetigt_at), vorher nie von selbst.

-- 1) Kennzeichen am Plan. auto_plan = vom Planer angelegt; auto_bestaetigt_at = Finns Bestätigung (null = Vorschlag).
alter table public.trade_plans add column if not exists auto_plan boolean not null default false;
alter table public.trade_plans add column if not exists auto_bestaetigt_at timestamptz;

-- 2) Regeln + Schalter, eine Zeile (id = 1). user_ids = IDs, für die geplant wird — die IDs stehen bewusst NUR in der DB
-- (Repo ist öffentlich). aktiv = nächtlicher Lauf (1–2 Uhr Dubai) an/aus; „Jetzt planen" geht auch bei aktiv = false.
-- regeln.firmen[]: namen = Firmenname nach Normalisierung (klein, nur a–z0–9, exakter Vergleich — „FundedNext Futures" ist
-- NICHT „FundedNext"), route tvv2|mt5v2, symbol (nur Futures, + Frontmonat), groessen = Kontogrößen, skaliert = Dollarwerte
-- und Menge gelten für 100k und wachsen mit der Größe. Je Phase: ziel_pct (Gewinnziel), boden_pct (statischer Max DD) oder
-- dd_usd (nur Risiko-Angabe), tp/sl/menge/puffer = [von, bis] (Zufall je Tranche), tp_max = höchstens je Trade (Consistency),
-- puffer_je_menge = Puffer abhängig von der Kontraktzahl. tp null = jeder Trade zielt aufs Endziel.
-- zeiten.fenster = Startfenster in deutscher Zeit mit Anteil; pause_firma_min = Abstand zwischen Tranchen DERSELBEN Firma
-- bei verschiedenen IDs; abstand_konto_s = Versatz der Konten innerhalb einer Tranche; abstand_id_min = Lücke je ID/PC.
create table if not exists public.auto_plan_regeln (
  id smallint primary key default 1 check (id = 1),
  aktiv boolean not null default false,
  user_ids uuid[] not null default '{}',
  regeln jsonb not null default '{"firmen": []}'::jsonb,
  zeiten jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.auto_plan_regeln enable row level security;

insert into public.auto_plan_regeln (id, regeln, zeiten) values (1,
'{"firmen": [
  {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "phasen": {
    "challenge": {"ziel_pct": 6, "dd_usd": 4500, "tp": [3450, 3550], "tp_max": 3600, "sl": null,
                  "menge": [2, 3], "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}},
  {"namen": ["apextrader", "apex"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "phasen": {
    "challenge": {"ziel_pct": 6, "tp": null, "sl": null, "menge": [4, 5], "menge_schritt": 1, "puffer": [100, 100]}}},
  {"namen": ["fundednext"], "route": "mt5v2", "groessen": [100000], "phasen": {
    "phase1": {"ziel_pct": 8, "boden_pct": 10, "tp": [6000, 8000], "sl": [2500, 3500], "menge": [2.1, 3.2], "menge_schritt": 0.1, "puffer": [100, 100]},
    "phase2": {"ziel_pct": 5, "boden_pct": 10, "tp": [6000, 8000], "sl": [2500, 3500], "menge": [2.1, 3.2], "menge_schritt": 0.1, "puffer": [100, 100]}}},
  {"namen": ["fundingpips"], "route": "mt5v2", "groessen": [100000], "phasen": {
    "phase1": {"ziel_pct": 10, "boden_pct": 12, "tp": [4200, 5000], "tp_max": 5000, "sl": [2500, 3500], "menge": [1, 1.5], "menge_schritt": 0.1, "puffer": [50, 75]},
    "phase2": {"ziel_pct": 8, "boden_pct": 12, "tp": [3500, 4000], "tp_max": 4000, "sl": [2500, 3500], "menge": [1, 1.5], "menge_schritt": 0.1, "puffer": [50, 75]}}},
  {"namen": ["the5ers"], "route": "mt5v2", "groessen": [100000, 200000], "skaliert": true, "phasen": {
    "phase1": {"ziel_pct": 8, "boden_pct": 10, "tp": [6000, 7000], "sl": [2000, 2500], "menge": [35, 45], "menge_schritt": 1, "puffer": [50, 75]},
    "phase2": {"ziel_pct": 5, "boden_pct": 10, "tp": [6000, 7000], "sl": [2000, 2500], "menge": [35, 45], "menge_schritt": 1, "puffer": [50, 75]}}}
]}'::jsonb,
'{"tz": "Europe/Berlin", "fenster": [["02:00", "14:00", 37], ["14:00", "15:30", 25], ["15:30", "16:30", 18], ["17:00", "20:00", 20]],
  "pause_firma_min": [25, 45], "abstand_konto_s": [60, 120], "abstand_id_min": 3}'::jsonb)
on conflict (id) do nothing;

-- 3) Protokoll je Lauf (nacht = automatisch, hand = „Jetzt planen"). Der Unique-Index ist der Claim: nur EIN Nachtlauf je Tag,
-- auch wenn zwei Railway-Instanzen gleichzeitig ticken.
create table if not exists public.auto_plan_lauf (
  id bigserial primary key,
  tag date not null,
  quelle text not null default 'hand',
  at timestamptz not null default now(),
  ergebnis jsonb
);
create unique index if not exists auto_plan_lauf_nacht_uq on public.auto_plan_lauf (tag) where quelle = 'nacht';
alter table public.auto_plan_lauf enable row level security;

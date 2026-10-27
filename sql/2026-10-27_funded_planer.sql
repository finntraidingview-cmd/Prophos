-- FUNDED-PLANER (27.10.2026, Finn: „Wir müssen einen Trade-Planer bauen, erst mal für alle Fundeds von Apex, weil die Trades nicht mehr
-- durchkommen … Erst mal alle Profile auswählbar, aber am Anfang nur Apex"). Regeln + Schalter des Funded-Planers (app.py fp_*), getrennt
-- von auto_plan_regeln (Challenge-Planer bleibt unberührt). Einspielen macht der Master nach der S2-Prüfung; aktiv bleibt false, bis Finn
-- die Vorschau (Admin → Funded-Planer) gesehen hat.

-- 1) Eine Zeile (id = 1), wie auto_plan_regeln. user_ids = IDs, für die geplant wird (stehen nur in der DB, Repo ist öffentlich).
-- firmen[]: name, namen = Firmenname nach _ap_norm (klein, nur a–z0–9), an = wird geplant, symbol, sl_pkt = SL-Weite in NQ-Punkten für die
-- Kontraktzahl, lock_usd = Lock des EOD-Trailing über der Größe. je_groesse: ziel_gewinn (Ziel = Zyklus-Start + ziel_gewinn), max_trade
-- (höchster TP je Trade, Apex-50-%-Consistency), kosten_eur (Kontokosten = Start der offenen Kosten des Hedges), dd (Max Drawdown).
-- zeiten: tz, von/bis = Startfenster, abstand_id_min = Lücke zwischen zwei Big Trades derselben ID, vorlauf_min = frühester Start ab jetzt.
create table if not exists public.funded_plan_regeln (
  id smallint primary key default 1 check (id = 1),
  aktiv boolean not null default false,
  user_ids uuid[] not null default '{}',
  firmen jsonb not null default '[]'::jsonb,
  zeiten jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.funded_plan_regeln enable row level security;
-- Keine Policy: nur Railway (Service-Key) liest und schreibt, wie bei auto_plan_regeln.

insert into public.funded_plan_regeln (id, aktiv, user_ids, firmen, zeiten) values (1, false,
  -- alle IDs der Gruppe Hermann Technologies (die Emin-Gruppe nicht); geplant werden ohnehin nur Funded-Konten einer Firma mit an = true
  coalesce((select array_agg(m.user_id) from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
            where g.name = 'Hermann Technologies'), '{}'),
'[
  {"name": "Apex Trader", "namen": ["apextrader", "apex"], "an": true, "symbol": "NQ", "sl_pkt": 60, "lock_usd": 100,
   "je_groesse": {"150000": {"ziel_gewinn": 15000, "max_trade": 7500, "kosten_eur": 550, "dd": 4000},
                  "100000": {"ziel_gewinn": 12000, "max_trade": 6000, "kosten_eur": 412.5, "dd": 3000}}},
  {"name": "Tradeify", "namen": ["tradeify"], "an": false},
  {"name": "Topstep", "namen": ["topstep"], "an": false},
  {"name": "Lucid Trading", "namen": ["lucidtrading", "lucid"], "an": false},
  {"name": "FundedNext Futures", "namen": ["fundednextfutures"], "an": false},
  {"name": "FTMO Futures", "namen": ["ftmofutures"], "an": false}
]'::jsonb,
'{"tz": "Asia/Dubai", "von": "02:30", "bis": "20:00", "abstand_id_min": [90, 150], "vorlauf_min": 15}'::jsonb)
on conflict (id) do nothing;

-- 2) Lauf-Protokoll: der Funded-Planer schreibt in auto_plan_lauf mit quelle = 'funded' (nur Läufe mit neuen Plänen/Ziel-Konten).
-- Der Unique-Index des Challenge-Nachtlaufs (quelle = 'nacht') ist davon nicht berührt — keine Änderung nötig.

-- Prüfen:
-- select aktiv, cardinality(user_ids), jsonb_path_query_array(firmen, '$[*] ? (@.an == true).name'), zeiten from public.funded_plan_regeln;
-- Scharf schalten (erst nach Finns OK zur Vorschau):
-- update public.funded_plan_regeln set aktiv = true, updated_at = now() where id = 1;

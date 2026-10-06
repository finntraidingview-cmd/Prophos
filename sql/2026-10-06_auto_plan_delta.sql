-- AUTO-PLANER DELTA-NEUTRAL (06.10.2026, Vertrag .claude/master/autoplan-delta-vertrag.md; Finn: „über alle IDs den ganzen Tag
-- möglichst delta-neutral im Markt — Long ≈ Short, nie dieselbe Firma über IDs gegenläufig"). app.py rechnet je Trade
-- delta_eur_pkt (Kontowert ÷ Polster × $ je NQ-Punkt), der Nachtlauf (jetzt 00:00 deutscher Zeit) vergibt die Richtung je Firma,
-- der Ausgleichs-Bot ändert nur geplante, nicht gestartete Auto-Pläne. Wiederholbar: jede Zeile darf mehrfach laufen.

-- 1) Protokoll jeder Umplanung (Bot oder Hand). Nur der Service-Key schreibt/liest (RLS an, keine Policy) — Frontend liest über
-- GET /admin/auto-plan/delta (umplanungen[] des Tages).
create table if not exists public.auto_plan_umplanung (
  id bigserial primary key,
  um timestamptz not null default now(),
  plan_id uuid,
  user_id uuid,
  firma text,
  von_richtung text,
  nach_richtung text,
  von_start timestamptz,
  nach_start timestamptz,
  grund text,
  quelle text not null default 'bot' check (quelle in ('bot', 'hand'))
);
create index if not exists auto_plan_umplanung_um_idx on public.auto_plan_umplanung (um desc);
alter table public.auto_plan_umplanung enable row level security;

-- 2) Bot-Parameter: regeln.ausgleich — vorhandene Werte bleiben (nur fehlende Schlüssel kommen dazu). Standard AUS:
-- aktiv = Bot-Takt, takt_min = Minuten zwischen zwei Läufen (00:00–19:30 dt, plus Extra-Lauf 14:00), zielband_pct =
-- |Netto| ≤ Band × Brutto, auto_start = neue Auto-Pläne gelten sofort als bestätigt. auto_plan_regeln.aktiv (Nachtlauf)
-- bleibt unberührt — Finn hat ihn pausiert.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{ausgleich}',
                          '{"aktiv": false, "takt_min": 10, "zielband_pct": 15, "auto_start": false}'::jsonb
                          || coalesce(regeln->'ausgleich', '{}'::jsonb)),
       updated_at = now()
 where id = 1;

-- 3) Startfenster deutscher Zeit laut Vertrag §2: 00:00–14:30 → 40 % · 14:30–17:30 → 40 % · 17:30–19:30 → 20 %
-- (vorher 02:00–14:00 37 % · 14:00–15:30 25 % · 15:30–16:30 18 % · 16:30–17:30 20 %, letzter Start 17:30).
update public.auto_plan_regeln
   set zeiten = zeiten || '{"fenster": [["00:00", "14:30", 40], ["14:30", "17:30", 40], ["17:30", "19:30", 20]]}'::jsonb,
       updated_at = now()
 where id = 1;

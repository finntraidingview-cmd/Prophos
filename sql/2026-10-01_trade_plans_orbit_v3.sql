-- Orbit V3 (01.10.2026, Finn: „Orbit wieder reaktivieren — Puls platziert die Order, das Tampermonkey-Script im
-- Puls-Chrome liest die Position, Fusion hedgt, Radar bleibt Backup"). Technisch ein Orbit-V2-Plan (route tvv2) mit
-- Fusion-Gegenhedge (hedge_eur/hedge_faktor wie die Winning Days Farm) — aber KEIN Winning Day: normaler Master-SL
-- statt Liquidations-Level, jedes Futures-Konto, eigene Kennung für Anzeige und WD-Filter.
-- Ohne diese Spalte wäre jeder tvv2-Plan mit hedge_eur > 0 im Frontend automatisch ein Winning Day (tpIstWdPlan).
alter table public.trade_plans add column if not exists orbit_v3 boolean not null default false;
comment on column public.trade_plans.orbit_v3 is 'Orbit V3: tvv2 + Fusion-Hedge, Schließen über Userscript im Puls-Chrome (Reader) + Radar-Backup; kein Winning Day';

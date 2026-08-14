-- ============================================================================
-- Prophos: trade_plans — MT5-Copier-Route (Etappe 3 Vollausbau, 15.08.2026)
--
-- Zweck: Trade-Pläne können ab jetzt über den eigenen MT5-Hedge-Copier laufen
-- statt über Duplikium. Damit die drei Erkennungs-Engines (Browser-atCheck,
-- mpWatch, Server-Wächter) und die neue MT5-Erkennung sich NIE gegenseitig
-- in die Pläne greifen, wird die Route explizit am Plan vermerkt:
--
--   route = NULL   → Bestandsverhalten (Duplikium bzw. Mirror, wie bisher)
--   route = 'mt5'  → Plan gehört der MT5-Copier-Erkennung; alle anderen
--                    Engines überspringen ihn mit einer additiven Skip-Zeile.
--
-- mt5_baseline hält die Kontostände zum Zeitpunkt planned→open:
--   { "master_balance": 12345.67, "hedge_balance": 2345.67, "at": "ISO" }
-- Daraus rechnet Prophos beim Trade-Ende das Master-P&L als Balance-Delta
-- ('Beweis oder leer': fehlt die Baseline, bleibt das Feld leer statt geraten).
-- Das Hedge-P&L kommt NICHT aus einer Balance-Differenz (das Hedge-Konto ist
-- von allen Mastern geteilt), sondern aus den vom Copier selbst geschlossenen
-- Deals (magic-partitioniert, strukturell beweisfest).
--
-- Beide Spalten nullable + ohne Default: Bestandszeilen und der komplette
-- Duplikium-Pfad bleiben unberührt (Finns Grundgesetz für Etappe 3).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.trade_plans
  add column if not exists route text;

alter table public.trade_plans
  add column if not exists mt5_baseline jsonb;

comment on column public.trade_plans.route is
  'NULL = Duplikium/Mirror (Bestand). ''mt5'' = eigener MT5-Hedge-Copier; nur die MT5-Erkennung fasst den Plan an.';

comment on column public.trade_plans.mt5_baseline is
  'Kontostände bei planned→open: {master_balance, hedge_balance, at}. Grundlage des Master-P&L (Balance-Delta). Fehlt sie, bleibt das P&L-Feld leer (Beweis oder leer).';

-- ============================================================================
-- Prophos: trade_plans.hedge_faktor (24.09.2026 spät, Winning-Day-Gegenhedge)
--
-- Faktor des Fusion-Gegenhedges: 1,0 = am Master-TP verliert Fusion in € so
-- viel, wie der Master in $ gewinnt (Verhältnis aus TP und SL im Plan-Popup).
-- hedge_eur bleibt der daraus GERECHNETE Betrag, den Panel/Copier bekommen
-- (Lots = eur / (tp_punkte × Punktwert)). NULL = Faktor nicht gesetzt (Betrag
-- kommt dann aus der Staffel oder von Hand).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.trade_plans add column if not exists hedge_faktor numeric;
comment on column public.trade_plans.hedge_faktor is
  'Fusion-Gegenhedge-Faktor (24.09.2026): 1,0 = am Master-TP verliert Fusion in € so viel, wie der Master in $ gewinnt; hedge_eur = gerechneter Betrag.';

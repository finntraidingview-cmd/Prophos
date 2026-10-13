-- Gruppen-Planer Emin: Startfenster 07:00–15:15 deutsche Zeit statt 07:00–17:20 (Finn 13.10.2026: „die Trades, die von 7:00 Uhr bis
-- 15:15 Uhr gestartet werden" → „ja"). Der Takt plant damit bis 15:00 nach (bis − 15 min Vorlauf).
update public.auto_plan_gruppe g set zeiten = g.zeiten || '{"bis": "15:15"}'::jsonb, updated_at = now()
  from public.id_gruppen i where i.id = g.gruppe_id and i.name = 'Emin';

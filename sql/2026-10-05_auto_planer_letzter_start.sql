-- AUTO-PLANER Zeitfenster (05.10.2026, Finn am ersten Tagesplan: „Ich will keinen Trade um 21:02 [Dubai] geplant haben, viel zu
-- spät — ab 17:18 sollte kein neuer Trade mehr dazukommen", dann „17:30 Ende, da keine neuen"). Letzter Start 17:30 deutscher
-- Zeit; das späte Fenster 17:00–20:00 wird zu 16:30–17:30, Anteile bleiben (37/25/18/20).
update public.auto_plan_regeln
set zeiten = jsonb_set(zeiten, '{fenster}',
  '[["02:00", "14:00", 37], ["14:00", "15:30", 25], ["15:30", "16:30", 18], ["16:30", "17:30", 20]]'::jsonb),
    updated_at = now()
where id = 1;

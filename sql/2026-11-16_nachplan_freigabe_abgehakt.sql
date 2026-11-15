-- Nachplan-Freigabe (Master, Finn 16.11.2026 ~03:30 Dubai: „hab alle abgehakt" → die Konten sollen heute noch getradet werden).
-- Der Nachtlauf 01:30 (auto_plan_lauf 1559) ließ 5 Konten mit „letzter Trade noch nicht erledigt (Überprüfen)" aus — die Freitagstrades
-- vom 13.11. standen da noch in Überprüfen, Finn hat sie erst ~03:00 abgehakt. „letzter Trade " ist ein FESTER Grund
-- (AP_NACHPLAN_FEST_GRUENDE), der Nachplan-Takt rechnet diese Konten also bis morgen nicht neu. Hier werden die 5 Einträge aus
-- ausgelassen entfernt (Original bleibt unter ergebnis.nachplan_freigabe erhalten) → der Takt (5 min) rechnet sie mit Würfel & Regeln neu.
-- Die zwei Topstep-Konten (Marc …20719220, Marco …48371084) bleiben drin: ihr Trade steht noch in Überprüfen.
update public.auto_plan_lauf l
set ergebnis = jsonb_set(
      jsonb_set(l.ergebnis, '{nachplan_freigabe}',
        coalesce((select jsonb_agg(e) from jsonb_array_elements(l.ergebnis->'ausgelassen') e
                  where e->>'konto_id' in ('079ed7b1-7ea3-4a1f-a1b4-a17755791189','25164c52-03ac-40e5-8eea-d6bb42f2ce9b',
                                           '555768b5-31d4-41f0-9617-01e6da7c02d8','7fcf07ef-ca74-44f0-9761-e1ed8ffa32e1',
                                           '8e50d86f-ce6e-4c19-802a-cbfcf3934c9d')), '[]'::jsonb)),
      '{ausgelassen}',
      coalesce((select jsonb_agg(e) from jsonb_array_elements(l.ergebnis->'ausgelassen') e
                where e->>'konto_id' not in ('079ed7b1-7ea3-4a1f-a1b4-a17755791189','25164c52-03ac-40e5-8eea-d6bb42f2ce9b',
                                             '555768b5-31d4-41f0-9617-01e6da7c02d8','7fcf07ef-ca74-44f0-9761-e1ed8ffa32e1',
                                             '8e50d86f-ce6e-4c19-802a-cbfcf3934c9d')), '[]'::jsonb))
where l.id = 1559 and l.tag = '2026-11-16' and l.quelle = 'nacht' and not (l.ergebnis ? 'nachplan_freigabe');

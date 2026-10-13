-- TAGE SAMMELN korrigiert (13.10.2026, Finn am Radar: „Alle von diesen drei Accounts haben bisher vier von fünf Tagen").
-- Gezählt wird je Berlin-Tag mit gestartetem Plan ab goal_since (11.10.) + goal_done_offset. Tage vor dem 11.10., Mini-Trades ohne
-- started_at und solche am alten Zwillings-Eintrag (Ina …4124, „100k funded next 14314124") fehlten — der Hand-Ausgleich war zu klein.
-- Stand danach: je 1 gestarteter Tag (13.10.) bzw. 0 (Ina …4124 neuer Eintrag) + Ausgleich = 4/5.
update public.accounts set goal_done_offset = 3 where id = 'eccaf2a2-b3f5-49a2-bd92-908348bbb2e2';   -- Moritz 100k 14244830 → Phase 2 (2 → 4)
update public.accounts set goal_done_offset = 3 where id = '8365342f-d3d3-44a5-a1e0-2b65108df3b3';   -- Ina 100k 14314123 → Phase 1 (3 → 4)
update public.accounts set goal_done_offset = 4 where id = 'fcfc93d1-4e56-4a73-b62a-8c7953603d99';   -- Ina 100k 14314124 → Phase 1 (3 → 4)

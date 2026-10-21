-- Marc Topstep 150k …33341330 bestanden, aber ohne „Phase bestanden → Nachfolger" abgehakt (21.10.2026, Finn: „Wir hatten bei Marc einen
-- Topstep-Account gepasst, aber der Trade ist nicht mehr da und ich kann den Nachfolger nicht anlegen"). Ablauf: Kette 2/2 (Plan 5399540c)
-- lief 13:30 Dubai in den TP (+1.650 $ Demo) auf 157.385,68 Start → ≈ 159.036 ≥ Ziel 159.000. Puls konnte danach nicht nachlesen —
-- TopstepX nimmt das bestandene Combine aus der Konto-Liste (8× konto_nicht_erreicht) —, tv_balance blieb 157.385,68, die Ziel-Wache sah
-- das Ziel nie, das Konto kam nie nach „Bestanden". 15:13 wurde der Plan mit „Nichts ändern" abgehakt → kein Archiv-Eintrag, kein
-- Nachfolger-Hinweis. Hier dasselbe wie „Phase bestanden" im Abhak-Dialog (_konto_archiv_eintragen): Archiv des Besitzers
-- {archived, reason 'passed_pending', at}. Danach zeigt Marcs Login „🎉 Account-Daten nachtragen" für den Express-Nachfolger.
update user_settings s
   set value = s.value || jsonb_build_object('85b52f34-f80e-4bdd-b700-3164fd22589b',
                 jsonb_build_object('archived', true, 'reason', 'passed_pending', 'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))),
       updated_at = now()
 where s.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and s.key = 'archive'
   and not (s.value ? '85b52f34-f80e-4bdd-b700-3164fd22589b');

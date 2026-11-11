-- FF2c (Finn 11.11.2026 07:14: „Wenn der zweite Trade noch läuft bis 18:00 Uhr Dubai-Zeit, scheißegal welche ID, kriege ich eine Nachricht auf mein Handy, und dann
-- greife ich da ein“): Einstellung alarm_offen (HH:MM Dubai, Standard 18:00) je Größe am Pump-Modell (tp_modus pump2). app.py fdp_pump_offen_tick meldet einen noch
-- offenen Trade des 2-Trade-Wegs ab dieser Uhrzeit einmal als 🔴 mit Push an die Master-IDs. Ohne den Schlüssel gilt im Code der Standard 18:00 — diese Datei macht ihn
-- nur in der Karte (Funded-Planer → Futures → Einstellungen) änderbar (fdp_regeln_aendern ändert nur vorhandene Schlüssel).
-- Idempotent: setzt den Schlüssel nur, wo er fehlt; Finns spätere Änderung bleibt. Erst NACH dem Code-Push einspielen (der alte Code kennt alarm_offen in den
-- Regeln nicht und zeigte ihn als „nur per SQL“ an — harmlos).
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case
      when f->>'tp_modus' = 'pump2' and jsonb_typeof(f->'je_groesse') = 'object' then
        f || jsonb_build_object('je_groesse', (
          select coalesce(jsonb_object_agg(g.key, case when jsonb_typeof(g.value) = 'object' and not (g.value ? 'alarm_offen')
                                                       then g.value || '{"alarm_offen": "18:00"}'::jsonb else g.value end), '{}'::jsonb)
          from jsonb_each(f->'je_groesse') g))
      else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.firmen) f, jsonb_each(case when jsonb_typeof(f->'je_groesse') = 'object' then f->'je_groesse' else '{}'::jsonb end) g
              where f->>'tp_modus' = 'pump2' and jsonb_typeof(g.value) = 'object' and not (g.value ? 'alarm_offen'));

-- Kontrolle: select f->>'name', g.key, g.value->>'alarm_offen' from funded_plan_regeln, jsonb_array_elements(firmen) f, jsonb_each(f->'je_groesse') g
--            where id = 1 and f->>'tp_modus' = 'pump2';

-- WEICHE „TV-KONTEN LESEN AUF" IN DER DB (29.10.2026, Finn: „Ich möchte nicht immer Railway-Variablen hinzufügen … der kann ja mit einem Klick
-- alles lesen"). Startwert: nur der PC von Chris (pc-c19p2l) — der Probelauf. Danach schaltet der Admin im Reiter „Konten aus Mail & TV"
-- (Zeile „TV-Konten lesen auf", Chip je PC bzw. „alle PCs"); app.py liest auto_plan_regeln.regeln.tv_konten_pcs (60 s gemerkt), die
-- Railway-Variable TV_KONTEN_PCS gilt nur noch, wenn der Schlüssel fehlt. Puls liest auf einem eingeschalteten PC weiter nur, wenn er frei
-- ist (tvkFrei: kein offener Plan, kein Start < 45 min, Puls/Polar/Signal/Heimweg/Big Trade frei).
-- Einspielen: Master nach Prüfer-OK — sinnvoll erst mit dem Code dazu (vorher liest app.py den Schlüssel nicht). Idempotent: setzt nur den einen
-- Schlüssel, alle anderen Regeln bleiben.
--
-- RÜCKNAHME (zurück auf die Railway-Variable):
--   update public.auto_plan_regeln set regeln = regeln - 'tv_konten_pcs' where id = 1;

update public.auto_plan_regeln
   set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{tv_konten_pcs}', '["pc-c19p2l"]'::jsonb, true),
       updated_at = now()
 where id = 1;

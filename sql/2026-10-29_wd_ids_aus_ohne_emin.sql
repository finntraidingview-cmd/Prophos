-- WD-Farmer: Emin nicht mehr „immer weglassen" (Finn 29.10.2026 ~23:20 Dubai, als Emin im Farmer: „Bei Emin soll die WD-Funktion
-- eins zu eins genau gleich sein … früher gesagt: bei den IDs von Emin nicht und bei den IDs von Hermann schon. In Zukunft alles genau
-- gleich. Nur soll Emin halt nur die IDs von ihm sehen und wir nur die IDs von uns."). Ursache laut S7: wd_farmer_regeln.ids_aus enthielt
-- Emin seit 23.09.2026 („Emin und Finn immer weglassen"), das Frontend (wdIdsAus) warf ihn überall raus. Die archivierte ID „Finn" bleibt
-- drin. Sicht/Statistik bleiben getrennt (wdSichtOk/_admGruppeOk, HT-Sicht). Emins WD-Konto Tradeify …0887 hat wd_farm = false — es fährt
-- erst, wenn Emin oder Finn den Farm-Haken setzt.
update public.wd_farmer_regeln
   set ids_aus = coalesce((select jsonb_agg(x) from jsonb_array_elements_text(ids_aus) x
                            where x <> '6cceb3f3-dc78-48ee-8668-26081da3e70f'), '[]'::jsonb)
 where id = 1;

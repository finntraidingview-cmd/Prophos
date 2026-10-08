-- STRAHLSUCHE ÜBER DIE FENSTERGRENZE EIN (08.10.2026, Finn → Master, live seit 04:29:03 UTC): Finn sah, dass 10–16 Uhr Dubai nur Longs
-- laufen, und fragte, ob der Bot das überhaupt anschaut. Beobachtung Slave 3 (04:06 UTC): Buch +3,8 €/Pkt, schlimmster Fall −112 € bei NQ −30,
-- alle helfenden Shorts lagen im Nachmittagsfenster (14:30–16:30 dt) — das Vorziehen „im eigenen Fenster" fand keinen Zug. Mit dem Schalter
-- darf die Suche Pläne aus späteren Fenstern in die nächsten 60 min vorziehen (alle Regeln bleiben), Hinausschieben bleibt im eigenen Fenster.
-- Wiederholbar. Rückbau: dieselbe Zeile mit 'false'.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{ausgleich,fenster_uebergreifend}', 'true'::jsonb, true),
       updated_at = now()
 where id = 1;
-- Prüfen: select regeln->'ausgleich'->'fenster_uebergreifend' from auto_plan_regeln where id = 1;

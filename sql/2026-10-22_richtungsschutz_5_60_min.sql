-- RICHTUNGSSCHUTZ: GESPERRTER START WARTET 5–60 MIN ZUFÄLLIG STATT FEST +10 MIN (Finn 22.10.2026: „nicht immer fix 10 Minuten, sondern
-- 5 bis 60 Minuten“). Betrifft die harte Sperre „Gegenrichtung gleiche ID × Firma läuft oder ist noch nicht gelesen“:
--   (1) Claim-Trigger trade_plans_gegenhedge: start_um = jetzt + 10 min + 20–40 s  →  jetzt + 5–60 min (Sekunden-genau gewürfelt)
--   (2) prophos_gegenhedge_konflikt (Neu starten / von Hand über prophos_gegenhedge_halten): ziel jetzt + 10 min → jetzt + 5–60 min
-- Die 90-s-Sperre gegen ANDERE IDs (Gegenhedge-Fenster) bleibt unverändert. Gegenstück im PC-Tab: rkVerschieben (prophos.html).
-- Sicher gegen Abschreibfehler: liest die LIVE-Definition, ersetzt genau die eine Stelle, bricht ab, wenn sie nicht (mehr) passt.
-- NOCH NICHT EINGESPIELT — wartet auf Finns OK.
do $$
declare
  d text;
  alt1 constant text := $x$now() + interval '10 minutes' + make_interval(secs => 20 + floor(random() * 20))$x$;
  neu1 constant text := $x$now() + make_interval(secs => 300 + floor(random() * 3300))$x$;
  alt2 constant text := $x$return query select now() + interval '10 minutes', u,$x$;
  neu2 constant text := $x$return query select now() + make_interval(secs => 300 + floor(random() * 3300)), u,$x$;
begin
  d := pg_get_functiondef('public.trade_plans_gegenhedge()'::regprocedure);
  if position(alt1 in d) = 0 then raise exception 'trade_plans_gegenhedge: Stelle „+10 min“ nicht gefunden — nichts geändert'; end if;
  execute replace(d, alt1, neu1);
  d := pg_get_functiondef('public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamp with time zone)'::regprocedure);
  if position(alt2 in d) = 0 then raise exception 'prophos_gegenhedge_konflikt: Stelle „+10 min“ nicht gefunden — nichts geändert'; end if;
  execute replace(d, alt2, neu2);
end $$;
-- random() in einer als STABLE deklarierten Funktion: sauber als VOLATILE (Prüfer 22.10.2026); prophos_gegenhedge_halten ruft sie einmal je Aufruf
alter function public.prophos_gegenhedge_konflikt(uuid, uuid, text, text, timestamp with time zone) volatile;

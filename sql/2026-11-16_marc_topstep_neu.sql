-- TS3 (16.11.2026, Finn: „Marc TopstepX ist gefixt (Login), alle neu planen“). Befund Slave 6 aus auto_plan_lauf 1559 (Nachtlauf 15.11. 21:30 UTC):
-- Marcs aktive Topstep-Challenges standen NICHT wegen des Logins aus, sondern 4 × „Pause-Tag Firma (Firmen-Würfel 85 %)“ für ID × Topstep heute,
-- 1 × „letzter Trade noch nicht erledigt (Überprüfen)“ (…20719220, Plan afecd411 seit 13.11. in review — braucht Abhaken + Balance lesen, nicht hier).
-- Weg wie TW4 bei Simon heute früh (sql/2026-11-16_tw4_simon_lucid_heute.sql): eine Zeile ID × Firma × Plan-Tag. Dann greifen Firmen- und Konto-Würfel
-- für Marc × Topstep heute nicht; alle anderen Regeln bleiben (Waage, Tagesdeckel, Liq, Zeitfenster, Richtung/Gegenrichtung, Grenzen je ID/Firma).
-- Der Nachplan-Takt (5 min) liest die Tabelle. Morgen wieder normal gewürfelt. Idempotent.
insert into public.planer_wuerfel_ausnahme (user_id, firma, tag, angelegt_von)
values ('6c206a34-c4a7-4352-8097-bb17366bcea1', 'Topstep', '2026-11-16', 'Master SQL (Finn 16.11.2026, TopstepX-Login gefixt)')
on conflict do nothing;

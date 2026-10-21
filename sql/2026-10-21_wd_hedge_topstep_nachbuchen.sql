-- Topstep-Winning-Days mit Fusion-Hedge: Hedge-Kosten nachbuchen (21.10.2026, Finn: „kurz gucken, ob alle richtig verbucht wurden").
-- Das kleine Erledigt-Popup (Radar / WD-Seite) behandelte Route tsv2 pauschal als „ohne Hedge": Fusion-Feld weg, slave_pl null
-- überschrieb den vom Hedge geschriebenen Fusion-P&L, und app.py hätte für tsv2 ohnehin nicht als wd_hedge gebucht. Seit .1493
-- laufen Topstep-WDs aber mit Fusion-Hedge → 4 Pläne seit 20.10. ohne Buchung (−271,71 €). Fix im Code: .1685.
-- Hier: slave_pl = mt5_baseline.hedge.pl (Deal-Historie, EUR, keine versuche_alt) und je Plan eine wd_hedge-Buchung wie
-- _wd_hedge_buchung — Konto des Besitzers wie bei seinen übrigen WD-Hedge-Buchungen (Login 488579), Datum = Tag des Abhakens (UTC).
-- Idempotent: nur Pläne ohne slave_pl, Buchung nur, wenn es noch keine mit dem notes-Schlüssel gibt.

update trade_plans p
   set slave_pl = (p.mt5_baseline->'hedge'->>'pl')::numeric
 where left(p.id::text, 8) in ('451c816c', '46b08941', 'c3cd1bd9', 'bbbf228c')
   and p.route = 'tsv2' and p.status = 'completed' and p.slave_pl is null
   and p.mt5_baseline->'hedge'->>'status' = 'geschlossen'
   and p.mt5_baseline->'hedge'->>'pl' is not null;

insert into transactions (user_id, account_id, account_name, account_firm, kind, amount, currency, occurred_at, notes, auto_generated)
select p.user_id, k.konto_id, k.konto_name, 'Fusion Markets', 'wd_hedge',
       round((p.mt5_baseline->'hedge'->>'pl')::numeric, 2), 'EUR', (p.completed_at at time zone 'UTC')::date,
       'Trade #' || left(p.id::text, 8) || ' WD-Hedge · ' || k.person || ' · ' || k.konto_name, true
  from trade_plans p
  join (values ('7b1bc9a3-94d3-4603-a232-c10fc2df3262'::uuid, '84715237-24f4-49ab-bef2-deb48fda5b5c'::uuid, 'Fusion Live ECHO', 'Chris'),
               ('32b854d1-866f-4e7e-ba0b-9bf63df2d993'::uuid, '9d5040d9-27b4-4633-ae26-34adc0f24fda'::uuid, 'Fusion Echo Slave (Echo)', 'Mike'))
       as k(user_id, konto_id, konto_name, person) on k.user_id = p.user_id
 where left(p.id::text, 8) in ('451c816c', '46b08941', 'c3cd1bd9', 'bbbf228c')
   and p.route = 'tsv2' and p.status = 'completed'
   and p.mt5_baseline->'hedge'->>'pl' is not null
   and not exists (select 1 from transactions t where t.kind = 'wd_hedge' and t.notes like 'Trade #' || left(p.id::text, 8) || ' WD-Hedge%');

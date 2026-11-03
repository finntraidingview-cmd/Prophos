-- PAYOUT ABGEHAKT → KONTO WIEDER IM WINNING-DAYS-FARMER (Finn 03.11.2026 ~17:35 Dubai über den Eingang: „sobald ich den Payout abhake, soll die ID
-- automatisch wieder drin sein … bei Aurel … soll einfach für den heutigen Tag mit drin sein").
-- Befund (Slave 5, nur lesend): der Zähler ist schon zurück (Payout-Anfrage → payout_anfrage_konto_felder: goal_done_offset 0, goal_wd_seit = Anfrage,
-- Korrektur 0) — FundedNext Futures 150k 103c974d seit 02.11. 23:05 UTC, Tradeify 150k 208e7af9 (Aurel) seit 02.11. 23:30 UTC; beide heute „erhalten".
-- Was das Konto draußen hält, steht in der Tageszeile wd_tagesplan:
--   103c974d: Zeile 03.11. „fertig" (Block 04:17 UTC durch), Konto aktiv false / „Ziel schon voll" — eingefroren aus der Zeit vor dem Reset
--             (wdAbgleich frischt nur offene Zeilen auf, prophos.html offenFuer); dasselbe steht schon in der Zeile 04.11.
--   208e7af9: Zeile 03.11. „geplant", Konto aktiv, aber nie gewürfelt (start_um null) — es wurde erst nach dem Würfeln wieder aktiv,
--             wdTick würfelt nur, solange tagZiel = heute.
-- TEIL A (sicher, sofort): Zeile 04.11. von 103c974d — der eingefrorene Hinweis raus, Konto aktiv. Der PC-Tab rechnet die Vorschau beim nächsten
--   Abgleich selbst neu (Zeile offen) und setzt „Ziel schon voll" nur wieder, wenn sein zielFortschritt wirklich voll sagt.
-- TEIL B (NUR AUF FINNS JA — das Farmer-Fenster 04:00–16:30 Dubai ist für heute vorbei, ein Start jetzt liegt in der US-Session):
--   heutige Zeilen wieder öffnen, Blockstart jetzt + 10–20 min (gestreut). Der PC-Tab der ID legt den Plan im nächsten Abgleich an (wdAbgleich (2),
--   ≥ 90 s nach der Schreibung), Startzeit aus wdKontoZeiten. Richtung: Finns Zeile behält ihre, Aurels Zeile gewürfelt.
-- Wiederholbar: A nur solange der Hinweis steht; B nur solange kein Plan am Konto hängt und die Zeile nicht läuft.

-- ── TEIL A ──
update public.wd_tagesplan w
   set konten = (select jsonb_agg(case when k->>'id' = '103c974d-b311-4ac4-9175-93eb6faaa32a' and coalesce(k->>'plan_id', '') = ''
                                       then k || jsonb_build_object('aktiv', true, 'hinweis', '') else k end order by o)
                   from jsonb_array_elements(w.konten) with ordinality as t(k, o)),
       status = case when w.status = 'leer' then 'geplant' else w.status end,
       updated_at = now()
 where w.tag = '2026-11-04' and w.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and w.start_um is null
   and exists (select 1 from jsonb_array_elements(w.konten) k
                where k->>'id' = '103c974d-b311-4ac4-9175-93eb6faaa32a' and k->>'hinweis' = 'Ziel schon voll' and coalesce(k->>'plan_id', '') = '');

/* ── TEIL B (auskommentiert — erst nach Finns Ja einspielen, Kommentarzeichen entfernen) ──
update public.wd_tagesplan w
   set konten = (select jsonb_agg(case when k->>'id' = '103c974d-b311-4ac4-9175-93eb6faaa32a'
                                       then k || jsonb_build_object('aktiv', true, 'hinweis', '') else k end order by o)
                   from jsonb_array_elements(w.konten) with ordinality as t(k, o)),
       status = 'geplant',
       start_um = date_trunc('minute', now() + interval '10 minutes' + make_interval(secs => floor(random() * 600))),
       updated_at = now()
 where w.tag = '2026-11-03' and w.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and w.status = 'fertig'
   and exists (select 1 from jsonb_array_elements(w.konten) k
                where k->>'id' = '103c974d-b311-4ac4-9175-93eb6faaa32a' and coalesce(k->>'plan_id', '') = '')
   and not exists (select 1 from public.trade_plans p where p.master_account_id = '103c974d-b311-4ac4-9175-93eb6faaa32a'
                    and (p.status in ('planned', 'open', 'review') or p.started_at >= now() - interval '20 hours'));

update public.wd_tagesplan w
   set start_um = date_trunc('minute', now() + interval '10 minutes' + make_interval(secs => floor(random() * 600))),
       richtung = case when random() < 0.5 then 'buy' else 'sell' end,
       reihenfolge = coalesce((select max(x.reihenfolge) from public.wd_tagesplan x where x.tag = w.tag), 0) + 1,
       updated_at = now()
 where w.tag = '2026-11-03' and w.user_id = '13905525-69d0-4949-b081-efdbc397e888' and w.status = 'geplant' and w.start_um is null
   and not exists (select 1 from public.trade_plans p where p.master_account_id = '208e7af9-ec38-40ed-aa1d-cb7b77048523'
                    and (p.status in ('planned', 'open', 'review') or p.started_at >= now() - interval '20 hours'));
*/

-- Kontrolle
select w.tag, w.name, w.status, w.start_um at time zone 'Asia/Dubai' as start_dubai, w.richtung,
       (select jsonb_agg(jsonb_build_object('id', left(k->>'id', 8), 'aktiv', k->'aktiv', 'hinweis', k->>'hinweis', 'plan', k->>'plan_id'))
          from jsonb_array_elements(w.konten) k) as konten
  from public.wd_tagesplan w
 where w.tag in ('2026-11-03', '2026-11-04')
   and w.user_id in ('48f272b4-913e-4598-a06a-1dcc3d5679fb', '13905525-69d0-4949-b081-efdbc397e888')
 order by w.tag, w.name;

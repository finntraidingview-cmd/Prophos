-- Topstep-WD-Fehlstarts 17.11.2026 früh nachholen. Finn ~06:30 Dubai: „Bei Simon … auf Proceed gedrückt … alle fehlgeschlagenen Winnings bei
-- Topstep neu planen, damit die gleich gemacht werden.“ Nichts wurde gesendet (order_signale: anker_fehlt bzw. „Konto-Auslöser verdeckt
-- (Time Sync Warning …)“, nie ein Klick).
--   Mike  38201ff1 Express …1691 WD BUY 3 MNQ (05:23, TopstepX nicht bedienbar/abgemeldet)        → 06:41:20 Dubai
--   Simon 5cd9f337 Express …6316 WD SELL 3 MNQ (06:30, Time-Sync-Dialog, Finn hat Proceed geklickt) → 06:38:40 Dubai
--   Simon 4be65fa2 Express …2392 WD SELL 3 MNQ (05:29, geclaimt ohne Ergebnis)                       → 06:45:30 Dubai
-- Abstände: Simon 06:38:40 / 06:45:30 (beide SELL Topstep, keine Gegenrichtung), nächster Simon-Start Apex 06:59; Mike nächster The5%ers 07:11.
-- Wie aktion „nachholen“: start_um neu, start_um_gestartet_at null, start_fehler.status 'neu'. Dazu wd_tagesplan.konten[] (start_um, status, um)
-- mitziehen — sonst setzt der PC-Tab-Abgleich wdAbgleich die alte Zeit zurück (Falle 27.10./05.11.). Guard: nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler',
                     coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb) || jsonb_build_object('status','neu',
                       'behoben','nachgeholt per SQL 17.11.2026 (Topstep: Time-Sync-Dialog/Login, Finn: alle neu planen)'))
from (values
  ('38201ff1'::text, timestamptz '2026-11-17 06:41:20+04'),
  ('5cd9f337'::text, timestamptz '2026-11-17 06:38:40+04'),
  ('4be65fa2'::text, timestamptz '2026-11-17 06:45:30+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;

update public.wd_tagesplan w
set konten = (select jsonb_agg(case when left(e.k->>'plan_id',8) = v.kurz
                                    then e.k || jsonb_build_object('start_um', to_jsonb(v.neu), 'status', 'planned', 'um', null)
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)
              left join (values ('38201ff1', '2026-11-17T02:41:20.000Z'), ('5cd9f337', '2026-11-17T02:38:40.000Z'),
                                ('4be65fa2', '2026-11-17T02:45:30.000Z')) v(kurz, neu) on v.kurz = left(e.k->>'plan_id',8)),
    updated_at = now()
where w.tag = date '2026-11-17'
  and exists (select 1 from jsonb_array_elements(w.konten) k where left(k->>'plan_id',8) in ('38201ff1','5cd9f337','4be65fa2'));

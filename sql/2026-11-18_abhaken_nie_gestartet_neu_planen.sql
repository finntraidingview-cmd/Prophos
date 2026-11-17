-- Finn 18.11.2026 ~03:30 Dubai (Screenshot Radar → Erledigt → Abhaken): „Das steht manchmal da, obwohl gar kein Trade gemacht wurde … die Trades,
-- die jetzt hier sind, alle neu planen für heute.“ Befund: Chris' PC war am 17.11. bis ~17:00 aus; beim Anlauf hat sein PC-Tab die verpassten Pläne
-- mit start_claim_art 'verbrauch' (= verpasst, nichts gestartet) geclaimt. Der Tages-Reset (app.py ap_tagesreset) wertete jeden Claim ohne Ergebnis als
-- „geclaimt, aber kein Ergebnis am Plan“ → „Überprüfen“ statt löschen → Konto blockiert, Planer heute übersprungen. (Fix im Tages-Reset separat.)
-- Neu für heute (Plan-Werte unverändert — an den Konten lief seitdem nichts). NICHT dabei: Moritz FTMO 511464160 (b5927c8a) — Bot meldete
-- „Handel am Konto gesperrt (trade_allowed = False)“, erst Konto prüfen.
-- Startzeiten Dubai, ≥ 30 min zu Gegenrichtung derselben ID, je Firma gestreut:
--   78f97aa2 Marc   Topstep 150k …9220  BUY  (tsv2)  → 06:12:50
--   e1d3e225 Chris  FTMO Fut 50k …9613  SELL (tvv2)  → 06:31:40
--   5ebca32c Chris  WD FTMO 50k …6819   SELL (tvv2)  → 10:07:20  (+ wd_tagesplan: heute Pause-Tag Firma → auf Finns Wort aktiv)
--   4395ddf7 Chris  FTMO CFD 100k …7804 SELL (mt5)   → 10:41:30
--   b16ec1a0 Chris  Apex 100k …0007     BUY  (tvv2)  → 11:23:50
--   a27777b5 Chris  Apex 100k …0005     BUY  (tvv2)  → 14:06:30
-- Guard: nur review, nie gestartet, nie an Orbit gesendet.

update public.trade_plans p
set status = 'planned', ended_at = null, start_um = v.neu, start_um_gestartet_at = null, start_claim_art = null,
    planned_for = date '2026-11-18',
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then (coalesce(p.mt5_baseline,'{}'::jsonb) - 'final') || jsonb_build_object('start_fehler',
                               (p.mt5_baseline->'start_fehler') || jsonb_build_object('status','neu',
                                 'behoben','neu geplant 18.11.2026 (Tages-Reset hatte nie gestarteten Plan nach Überprüfen geschoben, Finn)'))
                        else coalesce(p.mt5_baseline,'{}'::jsonb) - 'final' end,
    result_notes = coalesce(p.result_notes || E'\n', '') || 'Neu geplant 18.11.2026 per SQL (nie gestartet, Finn: für heute neu planen)'
from (values ('78f97aa2'::text, timestamptz '2026-11-18 06:12:50+04'),
             ('e1d3e225'::text, timestamptz '2026-11-18 06:31:40+04'),
             ('5ebca32c'::text, timestamptz '2026-11-18 10:07:20+04'),
             ('4395ddf7'::text, timestamptz '2026-11-18 10:41:30+04'),
             ('b16ec1a0'::text, timestamptz '2026-11-18 11:23:50+04'),
             ('a27777b5'::text, timestamptz '2026-11-18 14:06:30+04')) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.status = 'review' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, p.master_name, to_char(p.start_um at time zone 'Asia/Dubai','HH24:MI:SS') start_dubai;

-- WD-Tageszeile Chris 18.11.: Konto FTMO296819 (ef31f9f7) stand als Pause-Tag Firma ohne Plan → Plan eintragen, sonst räumt der Abgleich ihn weg
update public.wd_tagesplan w
set konten = (select jsonb_agg(case when e.k->>'id' = 'ef31f9f7-ccdc-4ebc-b2b3-19bdeda0d27d'
                                    then e.k || jsonb_build_object('plan_id', (select id::text from public.trade_plans where left(id::text,8) = '5ebca32c'),
                                                                   'start_um', '2026-11-18T06:07:20.000Z', 'status', 'planned', 'um', null,
                                                                   'aktiv', true, 'gesendet', false, 'ended', null,
                                                                   'hinweis', 'neu geplant 18.11. (Finn, trotz Pause-Tag Firma)')
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)), updated_at = now()
where w.tag = date '2026-11-18' and w.user_id = '7b1bc9a3-94d3-4603-a232-c10fc2df3262';

-- Würfel-Ausnahme je Konto für heute (wie Marc …7821 am 17.11.): kein Planer/Abgleich räumt die neu geplanten Pläne wegen Pause-Tag weg. Idempotent.
insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select p.user_id, null, p.master_account_id, date '2026-11-18', 'Master SQL (Finn 18.11.2026: nie gestartete Pläne vom 17.11. heute neu)'
from public.trade_plans p
where left(p.id::text,8) in ('78f97aa2','e1d3e225','5ebca32c','4395ddf7','b16ec1a0','a27777b5') and p.master_account_id is not null
  and not exists (select 1 from public.planer_wuerfel_ausnahme a where a.konto_id = p.master_account_id and a.tag = date '2026-11-18');

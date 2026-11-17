-- Ina Topstep-WD 150k PRO …8936 (Plan 16637d9a, SELL 3 MNQ) war 13:16 Dubai geclaimt, danach Tab-Neuladen 13:18, kein order_signal → nichts platziert.
-- Finn 17.11.2026 ~17:17 Dubai: „ja neu planen“ (Werbe-Popup in TopstepX von Hand weggeklickt; seit .2245 schließt Puls es selbst).
-- Neu 17:39:20 Dubai: Inas Starts 17:22 Lucid, 17:32 FundingPips, 18:11/18:25 Lucid → ≥ 5 min Abstand; einzige Topstep-Position der ID.
-- Ohne Gruppe in der Tageszeile → start_um dort mitziehen genügt. Guard: nichts gestartet/gesendet.
update public.trade_plans p
set start_um = timestamptz '2026-11-17 17:39:20+04', start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler',
                     coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb) || jsonb_build_object('status','neu',
                       'behoben','nachgeholt per SQL 17.11.2026 (Tab-Neuladen nach Claim, Finn: neu planen)'))
where p.id::text like '16637d9a%' and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null;

update public.wd_tagesplan w
set konten = (select jsonb_agg(case when e.k->>'plan_id' like '16637d9a%'
                                    then e.k || jsonb_build_object('start_um', '2026-11-17T13:39:20.000Z', 'status', 'planned', 'um', null)
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)), updated_at = now()
where w.tag = date '2026-11-17' and w.user_id = 'd1f5bcae-2129-49a4-8415-915ab6474a64';

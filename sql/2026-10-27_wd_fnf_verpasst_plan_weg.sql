-- Verpassten Winning-Day-Plan FundedNext Futures (ID „Finn + Pascal") vom 27.10. entfernen, damit der Farmer das Konto am 28.10.
-- wieder würfelt (Master 27.10.2026, Auftrag Finn „Winning Days neu platzieren").
-- Anlass: Plan 83fe175e wurde 18:33 Dubai geclaimt, Puls brach ab (FNF-Tradovate-Login ohne Konto-Umschalter). Der Plan steht seitdem auf
-- planned MIT Claim — der Server räumt nur ungeclaimte Farmer-Pläne früherer Tage weg (app.py /admin/wd-plaene), der PC-Tab zählt ihn
-- als „fremden" planned-Plan → wd_tagesplan 28.10.: „hat schon einen geplanten/laufenden Plan", an jedem Folgetag wieder.
-- Gleiche Schritte wie „Löschen" im Trade-Planer (tpLoeschenAusfuehren, prophos.html): erst aus dem Tagesplan austragen (nur wenn der
-- Block nicht läuft), dann den Plan löschen — nie eine plan_id im Tagesplan ohne Plan (sonst legt die Selbstheilung ihn neu an).
-- Nur, solange er nie gesendet/gestartet wurde.

-- 1) Austragen (Tageszeile 27.10. ist seit 18:52 „fertig", der Plan dort „verpasst")
update wd_tagesplan t
set konten = (select jsonb_agg(case when k->>'plan_id' = '83fe175e-772d-4c1a-9be2-a9cf442c529f'
                                    then k || '{"plan_id": null, "status": null, "start_um": null, "aktiv": false, "hinweis": "Plan von Hand gelöscht"}'::jsonb
                                    else k end order by i)
              from jsonb_array_elements(t.konten) with ordinality as e(k, i)),
    updated_at = now()
where t.tag = '2026-10-27' and t.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and t.status <> 'laeuft'
  and exists (select 1 from trade_plans p where p.id = '83fe175e-772d-4c1a-9be2-a9cf442c529f'
              and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null);

-- 2) Löschen
delete from trade_plans
where id = '83fe175e-772d-4c1a-9be2-a9cf442c529f' and status = 'planned' and started_at is null and orbit_gesendet_at is null;

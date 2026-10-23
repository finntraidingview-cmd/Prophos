-- Topstep 150k (Plan 026e1f76, Topstep-Kette 1/2) neu einplanen (Finn 23.10.2026 ~12:20 Dubai:
-- „Ich habe mich hier eingeloggt … ist gespeichert, müsste jetzt funktionieren. Gern für nachher neu planen").
-- Anlass: 04:12 Dubai 3× „TopstepX im Puls-Chrome nicht angemeldet" (pc-xxxxxx), die ID hatte sich nach .1719 noch nie von Hand
-- angemeldet — jetzt erledigt. Muster wie _ap_neu_starten / prophos-neu-starten-nach-fensterschluss: Startzeit frisch (4–8 min
-- gestreut), Claim leeren, start_fehler auf „neu". Nur dieser eine Plan, nur solange er noch nicht gestartet ist.
update trade_plans
set start_um = now() + interval '4 minutes' + random() * interval '4 minutes',
    start_um_gestartet_at = null,
    mt5_baseline = jsonb_set(mt5_baseline, '{start_fehler,status}', '"neu"'),
    updated_at = now()
where id = '026e1f76-669e-45fd-b1b6-f01932e9764b'
  and status = 'planned'
  and started_at is null
returning id, status, start_um at time zone 'Asia/Dubai' as start_um_dubai;

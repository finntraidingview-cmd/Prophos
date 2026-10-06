-- Auto-Planer: Startfenster bis 16:30 dt + Klumpen-Regel (Finn 07.10.2026)
-- „Alle Trades sollen bis spätestens 16:30 deutscher Zeit (18:30 Dubai) gestartet sein." → Fenster 00:00–14:30 50 % ·
-- 14:30–16:30 50 %, zeiten.start_bis 16:30 (der Code kappt auch ohne diesen Wert bei 16:30, AP_START_BIS_STANDARD).
-- „zwei Tradeify-Last-Trades à ~720 € hintereinander short = 1.400 € auf einer Seite, das ist überhebelt" →
-- regeln.ausgleich.max_netto_eur 800 (|Netto-Einsatz| zu jeder Minute), paar_ab_eur 300 (großer Trade braucht ein Gegenstück
-- binnen ±30 min). Die Werte sind auch die Code-Standards; die Datei macht sie in der DB sichtbar und änderbar.
-- Nichts anderes in zeiten/regeln wird angefasst (jsonb ||, nur die genannten Schlüssel).

update public.auto_plan_regeln
set zeiten = coalesce(zeiten, '{}'::jsonb)
             || jsonb_build_object('fenster', '[["00:00","14:30",50],["14:30","16:30",50]]'::jsonb,
                                   'start_bis', '16:30'),
    regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{ausgleich}',
                       coalesce(regeln->'ausgleich', '{}'::jsonb)
                       || jsonb_build_object('max_netto_eur', 800, 'paar_ab_eur', 300)),
    updated_at = now()
where id = 1;

-- Prüfen:
-- select zeiten->'fenster', zeiten->>'start_bis', regeln->'ausgleich' from public.auto_plan_regeln where id = 1;

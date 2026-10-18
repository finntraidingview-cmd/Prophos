-- 19.10.2026 (Finn, 00:00 Dubai): „Es wurden richtig viele Accounts aufgeladen … vor allem bei Apex nicht alle Accounts in einem
-- Tag machen, weil da etwas schiefgeht … 2 bis 3 Trades pro ID bei Apex, bis ich sage: Ändere was." CFD-Firmen weiter wie immer.
-- Neues Regel-Feld max_konten_tag = [von, bis] je Firma: der Planer (ap_tagesdeckel in app.py) gibt je ID × Firma an einem Tag
-- höchstens so vielen Konten einen Plan, laufende/heute geplante/heute beendete zählen mit; der Rest steht sichtbar in „ausgelassen".
-- Aufheben: das Feld wieder entfernen (regel - 'max_konten_tag').
update auto_plan_regeln
set regeln = jsonb_set(
  regeln, '{firmen}',
  (select jsonb_agg(case when (f->'namen') ? 'apex' then f || '{"max_konten_tag": [2, 3]}'::jsonb else f end order by o)
   from jsonb_array_elements(regeln->'firmen') with ordinality t(f, o)))
where id = 1;

-- Kontrolle
select f->'namen' as namen, f->'max_konten_tag' as max_konten_tag
from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f
where id = 1 and (f->'namen') ? 'apex';

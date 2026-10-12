-- MINDESTTAGE RÜCKWIRKEND (Finn 13.10.2026: „bei den bestehenden Accounts wurden ja bestimmt schon ein paar Tage gesammelt — das fehlt da noch").
-- Befund 13.10.2026 02:20 Dubai: 91 Konten mit goal_kind trading_days, alle mit goal_since 11.10.2026 (sql/2026-10-12_fundednext_mindesttage.sql);
-- 81 davon haben in trade_plans schon Berlin-Tage mit gestartetem Plan VOR dem 11.10. (zusammen 310 Tage), die der Zähler wegen goal_since ausblendet.
-- Weg: die Alt-Tage als goal_done_offset festschreiben, goal_since bleibt. Nicht goal_since lösen — der Auto-Planer (app.py ap_tage_ist) sieht nur
-- Pläne der letzten 30 Tage, das Frontend (zielFortschritt) alle: beide zählen offset + Tage ab goal_since, so bleibt der Stand überall gleich.
-- Zählweise = dieselbe wie zielFortschritt/ap_tage_ist: Tag (Europe/Berlin) von trade_plans.started_at, Konto als Master, jeder Status.
-- Nur Konten mit goal_done_offset 0 (einmalig; ein von Hand gesetzter Offset bleibt). Wiederholbar: beim zweiten Lauf trifft es nichts mehr,
-- weil der Offset dann > 0 ist — außer Konten ohne Alt-Tage, die bleiben 0. Korrektur je Konto: Accounts → Badge „Tage x/5" klicken (Offset).
-- Grenze: ein Konto, dessen Phase früher IM SELBEN Eintrag umgestellt wurde, zählt hier auch die Tage der alten Phase mit — dann Offset von Hand.

with alt as (
  select a.id, count(distinct (p.started_at at time zone 'Europe/Berlin')::date) as tage
  from accounts a
  join trade_plans p on p.master_account_id = a.id and p.started_at is not null
  where a.goal_kind = 'trading_days' and a.goal_since is not null
    and coalesce(a.goal_done_offset, 0) = 0
    and (p.started_at at time zone 'Europe/Berlin')::date < a.goal_since
  group by a.id
)
update accounts a set goal_done_offset = alt.tage
from alt where alt.id = a.id and alt.tage > 0;

-- Kontrolle: Stand je Konto (Offset + Tage ab goal_since) gegen das Ziel
-- select name, goal_done_offset, goal_target, goal_since from accounts where goal_kind = 'trading_days' order by goal_done_offset desc;

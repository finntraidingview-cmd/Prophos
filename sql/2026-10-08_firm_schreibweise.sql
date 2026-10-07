-- 08.10.2026 — Audit Richtungsschutz (Slave-Terminal, Auftrag Master/Finn „nicht selbst gegeneinander hedgen"):
-- accounts.firm trug „MyFoundedFutures" (2 Konten) neben „MyFundedFutures" (6). Der Richtungsschutz schlüsselt je ID+Firma —
-- zwei Schreibweisen = zwei Firmen = Loch. Code (ap_firma_key/_firm_norm, firmNormRichtung) führt die Schreibweisen seit .1197
-- zusammen; hier zusätzlich die Daten geraderücken.

-- Prüf-Select VORHER: alle Schreibweisen je normalisiertem Schlüssel (mehr als eine Zeile je Schlüssel = Variante)
select lower(regexp_replace(coalesce(firm, ''), '[^a-z0-9]', '', 'gi')) as schluessel, firm, count(*) as n
from accounts group by 1, 2 order by 1, 3 desc;

update accounts set firm = 'MyFundedFutures' where firm = 'MyFoundedFutures';

-- Prüf-Select NACHHER: Varianten, die sich nur in Groß-/Kleinschreibung oder Sonderzeichen unterscheiden
select a.firm, b.firm, count(*) over () as varianten
from (select distinct firm from accounts) a join (select distinct firm from accounts) b
  on a.firm < b.firm and lower(regexp_replace(a.firm, '[^a-z0-9]', '', 'gi')) = lower(regexp_replace(b.firm, '[^a-z0-9]', '', 'gi'));

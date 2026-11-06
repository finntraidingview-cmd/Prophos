-- DD1 (06.11.2026, Finn: „Schablone und Nachfolger-Anlegen IMMER mit Max Drawdown“): Bestand ohne accounts.max_drawdown nachtragen.
-- Anlass: eine FundingPips Phase 2 entstand über „Review“ (Nachfolger-Assistent) mit leerem Feld, der Wert wurde danach von Hand eingetragen.
-- Stand 06.11.2026 (Vorschau als SELECT gegen die Live-DB): 22 aktive Konten — The5%ers phase1 7×, Tradeify CFD phase1 6×, FundedNext phase1 3×,
-- FundingPips phase1 2×, FTMO phase1 2×, Apex funded 1×, The5%ers funded_cfd 1×. Alle Quellen waren sich je Konto einig (Vorgänger = Schablone = Kernwert).
--
-- Dieselben Quellen und dieselbe Reihenfolge wie der Browser (sucDdVorschlag/sucDdErmitteln) und app.py (konto_dd_aus_regel):
--   1) Vorgänger mit Wert (user_settings 'parents')          — Wissen je Konto (z. B. FundingPips Flex 12 %), geht vor
--   2) Schablone bulk_vorlagen Firma × Typ × Größe, aktiv     — nur wenn sich alle passenden Schablonen einig sind
--   3) Funded CFD: funded_cfd_plan_regeln je_groesse.dd
--   4) Firmen-Kernwert auto_plan_regeln: je_groesse.dd_usd → (je_groesse.dd_pct | dd_pct) × Größe → dd_usd nur für eine Größe aus groessen
-- Nie: Live (Fusion), Winning Days, deaktivierte oder archivierte Konten, Konten ohne erkennbare Größe, FundingPips mit „Flex“ im Namen (12 % weiß nur Finn).
-- Größe: account_size → starting_balance → Name („100k …“, Namensregel „<Größe> <External ID> → <Phase>“).
-- Vorgänger vor Schablone (bewusst, wie der Nachfolger-Assistent seit 13.07.2026): der Wert am Vorgänger ist Wissen je Konto (FundingPips Flex 12 %);
-- im Bestand vom 06.11.2026 trifft das genau ein Konto, und dort sind Vorgänger und Kernwert gleich.
--
-- Leser von max_drawdown (geprüft 06.11.2026, Finn: „damit wird nichts gerechnet“ — stimmt nicht ganz): FundingPips Flex/Standard (ap_konto_flex; 10 % = Standard
-- wie bei leerem Feld, also unverändert), Liq-Level in Live Trades (_lt_liq: vorher „kein Max-Drawdown am Konto“), Tradeify-WD-Zyklusprüfung, Funded-Hedge-Satz
-- × Max DD und Auto-Hedge-Vorschlag im Plan-Modal, Radar-Boden-Rückfall. Überall vorher „kein Wert“, jetzt der Firmen-Kernwert.
--
-- Idempotent: schreibt nur Zeilen mit max_drawdown is null. Ein zweiter Lauf ändert nichts.
-- Vorschau ohne Schreiben: den Block ab „with“ bis vor „update“ nehmen und „select * from werte“ anhängen.

with
arch as (
  select distinct e.key as acc_id
  from user_settings s, jsonb_each(s.value::jsonb) e
  where s.key = 'archive' and coalesce((e.value->>'archived')::boolean, false)
),
par as (
  select distinct on (e.key) e.key as acc_id, e.value #>> '{}' as parent_id
  from user_settings s, jsonb_each(s.value::jsonb) e
  where s.key = 'parents'
  order by e.key
),
basis as (
  select a.id, a.name, a.account_type,
         lower(regexp_replace(coalesce(a.firm, ''), '[^a-zA-Z0-9]', '', 'g')) as fkey,
         coalesce(nullif(a.account_size, 0), nullif(a.starting_balance, 0),
                  (substring(a.name from '(?i)(\d{2,3})\s*k\M'))::numeric * 1000) as groesse   -- wie app.py/kontoGroesseAnzeige: 2–3 Ziffern + k
  from accounts a
  where a.max_drawdown is null
    and a.deaktiviert_at is null
    and coalesce(a.account_type, '') in ('challenge', 'phase1', 'phase2', 'funded', 'funded_cfd')
    and not exists (select 1 from arch where arch.acc_id = a.id::text)
    and not (lower(regexp_replace(coalesce(a.firm, ''), '[^a-zA-Z0-9]', '', 'g')) = 'fundingpips' and a.name ~* 'flex')
),
regel as (
  select lower(n.n) as fkey, f
  from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') f, jsonb_array_elements_text(f->'namen') n(n)
  where r.id = 1
),
fcp as (
  select lower(n.n) as fkey, f
  from funded_cfd_plan_regeln r, jsonb_array_elements(r.firmen) f, jsonb_array_elements_text(f->'namen') n(n)
  where r.id = 1
),
werte as (
  select b.*,
    (select v.max_drawdown from par p join accounts v on v.id::text = p.parent_id
      where p.acc_id = b.id::text and v.max_drawdown > 0) as w_vorgaenger,
    (select case when count(distinct v.max_drawdown) = 1 then min(v.max_drawdown) end from bulk_vorlagen v
      where v.aktiv and lower(regexp_replace(coalesce(v.firm, ''), '[^a-zA-Z0-9]', '', 'g')) = b.fkey
        and v.account_type = b.account_type and coalesce(v.account_size, v.starting_balance) = b.groesse and v.max_drawdown > 0) as w_vorlage,
    (select (x.f->'je_groesse'->(b.groesse::bigint::text)->>'dd')::numeric from fcp x
      where b.account_type = 'funded_cfd' and x.fkey = b.fkey limit 1) as w_fcp,
    (select coalesce(
        nullif((x.f->'je_groesse'->(b.groesse::bigint::text)->>'dd_usd')::numeric, 0),
        nullif(round(b.groesse * coalesce(nullif((x.f->'je_groesse'->(b.groesse::bigint::text)->>'dd_pct')::numeric, 0), (x.f->>'dd_pct')::numeric) / 100), 0),
        case when (x.f->'groessen') @> to_jsonb(b.groesse::bigint) then nullif((x.f->>'dd_usd')::numeric, 0) end)
      from regel x where x.fkey = b.fkey limit 1) as w_kernwert
  from basis b
  where b.groesse > 0
)
update accounts a
set max_drawdown = coalesce(w.w_vorgaenger, w.w_vorlage, w.w_fcp, w.w_kernwert),
    updated_at = now()
from werte w
where a.id = w.id
  and a.max_drawdown is null
  and coalesce(w.w_vorgaenger, w.w_vorlage, w.w_fcp, w.w_kernwert) > 0;

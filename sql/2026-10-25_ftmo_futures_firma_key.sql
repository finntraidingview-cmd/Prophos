-- FTMO Futures als eigene Firma im DB-Firmenschlüssel (Finn 25.10.2026: „inklusive eigenem Firmenschlüssel für FTMO Futures").
-- prophos_firma_key machte aus „FTMO Futures" per strpos 'ftmo' den Schlüssel 'FTMO' — damit hätten Firmen-Abstand und Gegenrichtungs-
-- Riegel FTMO-Futures-Pläne mit den CFD-Plänen von FTMO in einen Topf geworfen. Neu: eigene Zeile VOR 'ftmo' — „ftmo" UND „futur" im
-- Namen → 'FTMO Futures' (wie app.py _firm_norm, Frontend firmNormRichtung). Sonst unverändert gegenüber
-- sql/2026-10-23_tradeify_cfd_firma_key.sql; tools/selftest_auto_firmen_abstand.py prüft den Gleichlauf mit _firm_norm gegen diese Datei.
-- Einspielen VOR dem ersten FTMO-Futures-Plan, idempotent (create or replace).

create or replace function public.prophos_firma_key(name text) returns text
language plpgsql immutable as $$
declare
  f text := lower(btrim(coalesce(name, '')));
begin
  -- gleiche Reihenfolge wie app.py _firm_norm / _FIRM_RULES (tools/selftest_auto_firmen_abstand.py prüft den Gleichlauf)
  if f = '' then return '—'; end if;
  if strpos(f, '5%er') > 0 or strpos(f, '5ers') > 0 or strpos(f, 'five percent') > 0 then return 'The5%ers'; end if;
  if strpos(f, 'futur') > 0 and (strpos(f, 'fundednext') > 0 or strpos(f, 'funded next') > 0
                                 or strpos(f, 'foundednext') > 0 or strpos(f, 'founded next') > 0) then return 'FundedNext Futures'; end if;
  if (strpos(f, 'funded') > 0 or strpos(f, 'founded') > 0) and strpos(f, 'futur') > 0 then return 'MyFundedFutures'; end if;
  if strpos(f, 'tradeify') > 0 and strpos(f, 'cfd') > 0 then return 'Tradeify CFD'; end if;
  if strpos(f, 'ftmo') > 0 and strpos(f, 'futur') > 0 then return 'FTMO Futures'; end if;
  if strpos(f, 'apex') > 0 then return 'Apex Trader'; end if;
  if strpos(f, 'tradeify') > 0 then return 'Tradeify'; end if;
  if strpos(f, 'fundednext') > 0 or strpos(f, 'founded next') > 0 or strpos(f, 'foundednext') > 0 then return 'FundedNext'; end if;
  if strpos(f, 'fundingpips') > 0 or strpos(f, 'funding pips') > 0 then return 'FundingPips'; end if;
  if strpos(f, 'topstep') > 0 then return 'Topstep'; end if;
  if strpos(f, 'ftmo') > 0 then return 'FTMO'; end if;
  if strpos(f, 'alpha') > 0 then return 'Alpha Future'; end if;
  if strpos(f, 'fusion') > 0 then return 'Fusion Markets'; end if;
  if strpos(f, 'lucid') > 0 then return 'Lucid Trading'; end if;
  return btrim(coalesce(name, ''));
end $$;
-- Prüfen: select prophos_firma_key('FTMO Futures'), prophos_firma_key('FTMO');   -- → FTMO Futures | FTMO

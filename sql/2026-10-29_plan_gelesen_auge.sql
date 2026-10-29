-- NOVA-ENDLESUNG AUS DEM TOPSTEPX-AUGE (29.10.2026, Finn 06:00 Dubai: „Es ist 1:1 der Profit aus TopstepX … man muss gar nicht erst auf
-- Puls warten"; prophos.html tsxAugeEndeUrteil/tsxAugeEndeSchreiben). Nach dem Ende eines Topstep-V2-Plans (route tsv2) schreibt der
-- PC-Tab eine bewiesene Auge-Lesung als Endlesung: mt5_baseline.final.quelle = 'auge' mit final.balance_end (Flach-Beweis des Auges,
-- Konto exakt, zwei gleiche RP&L-Lesungen ≥ 2 s nach dem Flach, Balance-Differenz = RP&L-Delta). Danach liest Puls diesen Plan nicht mehr.
--
-- (1) prophos_plan_gelesen: 'auge' zählt für tsv2 wie 'puls' (Prüfer S2 zu f34087b3: rkPlanGelesen im Frontend gab die Gegenrichtung
--     schon frei, der DB-Riegel prophos_gegenrichtung_frei_konto / prophos_gegenhedge_konflikt lehnte bis zum Abhaken ab — Muster 19.10.).
--     Funktion 1:1 wie live (gelesen 29.10.2026), nur die eine Bedingung dazu, dieselbe balance_end > 0-Prüfung.
-- (2) accounts.tv_balance_quelle darf 'auge' sein (die Konto-Balance aus dieser Lesung; bis zum Einspielen schreibt der PC-Tab 'puls').
--
-- Einspielen: Master nach Prüfer-OK (nicht vom Slave). Idempotent.
--
-- RÜCKNAHME:
--   create or replace function public.prophos_plan_gelesen(p_plan uuid) … wie unten, aber in der tvv2/tsv2-Zeile ohne
--     „or (p.route = 'tsv2' and fin->>'quelle' = 'auge')"
--   alter table public.accounts drop constraint if exists accounts_tv_balance_quelle_check;
--   update public.accounts set tv_balance_quelle = 'puls' where tv_balance_quelle = 'auge';
--   alter table public.accounts add constraint accounts_tv_balance_quelle_check
--     check (tv_balance_quelle is null or tv_balance_quelle in ('puls', 'dashboard', 'mt5'));

create or replace function public.prophos_plan_gelesen(p_plan uuid)
 returns boolean
 language plpgsql
 stable security definer
 set search_path to 'public'
as $function$
declare
  p record;
  fin jsonb;
  bn jsonb;
  zahl constant text := '^-?[0-9]+(\.[0-9]+)?$';
begin
  select status, route, ended_at, master_pl, mt5_baseline into p from public.trade_plans where id = p_plan;
  if not found or p.status is distinct from 'review' or p.ended_at is null or p.master_pl is null then
    return false;
  end if;
  fin := case when jsonb_typeof(p.mt5_baseline->'final') = 'object' then p.mt5_baseline->'final' end;
  bn  := case when jsonb_typeof(p.mt5_baseline->'bal_nach') = 'object' then p.mt5_baseline->'bal_nach' end;
  if p.route in ('tvv2', 'tsv2') then
    return coalesce(fin is not null and (fin->>'quelle' = 'puls' or fin->>'balance_quelle' = 'reader'
                                         or (p.route = 'tsv2' and fin->>'quelle' = 'auge'))
                    and coalesce(fin->>'balance_end', '') ~ zahl and (fin->>'balance_end')::numeric > 0, false);
  elsif p.route in ('mt5', 'mt5v2') then
    return coalesce(fin is not null and bn is not null and bn->>'ok' = 'true'
                    and coalesce(bn->>'balance', '') ~ zahl and (bn->>'balance')::numeric > 0, false);
  end if;
  return false;
end $function$;

alter table public.accounts drop constraint if exists accounts_tv_balance_quelle_check;
alter table public.accounts add constraint accounts_tv_balance_quelle_check
  check (tv_balance_quelle is null or tv_balance_quelle in ('puls', 'dashboard', 'mt5', 'auge'));

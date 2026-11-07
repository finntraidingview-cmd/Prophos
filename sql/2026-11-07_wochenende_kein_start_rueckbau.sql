-- RÜCKBAU zu sql/2026-11-07_wochenende_kein_start.sql (WE1, 07.11.2026). Wiederholbar.
-- 1) Claim-Riegel weg  2) final_halten ohne die WE1-Zeile (Textersatz zurück)  3) Hilfsfunktionen weg. Alles in EINER Transaktion: findet der
-- Textersatz die Zeile nicht, bricht der Rückbau ab und nichts ist geändert.
begin;
drop trigger if exists trade_plans_a00_wochenende on public.trade_plans;
drop function if exists public.trade_plans_a00_wochenende();

do $patch$
declare
  def text;
  zeile text := $z$  ziel := public.prophos_naechster_handelstag(ziel);   -- WE1 (07.11.2026): nie aufs Markt-Wochenende
$z$;
begin
  def := pg_get_functiondef('public.trade_plans_a_final_halten()'::regprocedure);
  if position(zeile in def) > 0 then
    execute replace(def, zeile, '');
  end if;
  if position('prophos_naechster_handelstag' in pg_get_functiondef('public.trade_plans_a_final_halten()'::regprocedure)) > 0 then
    raise exception 'final_halten ruft prophos_naechster_handelstag noch (Zeile nicht exakt gefunden) — Rückbau abgebrochen, nichts gelöscht';
  end if;
end $patch$;

drop function if exists public.prophos_naechster_handelstag(timestamptz);
drop function if exists public.prophos_markt_wochenende(timestamptz);

commit;

-- START-CLAIM-ART (23.10.2026, Vorstufe zu sql/2026-10-23_waage_deckel.sql — VOR ihr einspielen; Master nach Prüfung des Waage-Deckels:
-- „Der Deckel darf Verbrauchs-Claims (Ziel erreicht / Manuelle Arbeit / verpasst) NIE sperren"). Bisher schrieb der PC-Tab für einen echten
-- Start und für einen Verbrauch (Plan wird nur abgeschlossen, damit er nie mehr feuert) exakt dasselbe Update { start_um_gestartet_at: jetzt }
-- — ein Claim-Riegel konnte beides nicht unterscheiden. Jetzt schreibt der Tab im selben Update start_claim_art = 'start' (echter Start) bzw.
-- 'verbrauch' (Archiv, Manuelle Arbeit, Ziel erreicht, verpasst). Kein Feld (Tab noch nicht neu geladen) = NULL.
--   1) Spalte trade_plans.start_claim_art (text, ohne Standard).
--   2) Wird der Claim zurückgenommen (start_um_gestartet_at → NULL: Verschieben, Neu einplanen, Nachholen), leert ein Trigger die Art mit —
--      sonst könnte ein alter 'verbrauch' an einem später echt gestarteten Plan kleben und ihn an einem Riegel vorbeilassen.
-- Idempotent (add column if not exists / create or replace / drop trigger if exists).

alter table public.trade_plans add column if not exists start_claim_art text;
comment on column public.trade_plans.start_claim_art is
  'Art des Claims (start_um_gestartet_at): start = echter Start, verbrauch = Plan abgeschlossen ohne Start (Archiv, Manuelle Arbeit, Ziel erreicht, verpasst); NULL = Tab ohne Feld. Seit 23.10.2026, Waage-Deckel.';

create or replace function public.trade_plans_claim_art_leeren()
returns trigger
language plpgsql as $$
begin
  new.start_claim_art := null;
  return new;
end $$;

drop trigger if exists trade_plans_claim_art_leeren on public.trade_plans;
create trigger trade_plans_claim_art_leeren
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is not null and new.start_um_gestartet_at is null)
  execute function public.trade_plans_claim_art_leeren();

-- Probe (nur lesen):  select start_claim_art, count(*) from public.trade_plans where start_um_gestartet_at > now() - interval '1 day' group by 1;

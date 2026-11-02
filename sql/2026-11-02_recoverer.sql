-- RECOVERER (02.11.2026, Finn 04:30 „ja, bauen"; Konstrukt .claude/master/berichte/2026-11-01_apex-wd-konstrukt.md, Variante B):
-- Apex-Winning-Days nach einem Verlusttag im Payout-Zyklus. Anlass Mike 150k …0001: −3.998 $ am 30.10.2026, Admin zeigte 3.000 $
-- anfragbar, obwohl Apex erst wieder auszahlt, wenn der Zyklus-Profit ≥ 2 × bester Tag ist. Die Regel hebt WD-Ziel und Hedge-Satz
-- linear nach dem schlechtesten Einzeltag an (−2.000 → 750 $ / 400 € je 1.000 $, −4.000 → 1.500 $ / 300 €), erst ab Zyklus 2, nur
-- Apex, nur Konten im Farmer, bis Profit ≥ 2 × bester Tag. Gerechnet wird auf Railway (app.py wd_zyklus_stand / wd_zyklus_werte),
-- hier liegen nur die Parameter und der Schalter je Konto.
--
-- 1) wd_farmer_regeln.zyklus_regel (jsonb): eigene Spalte, NICHT in vorplan.regeln — wdHedgeSpeichern (prophos.html) baut vorplan
--    beim Auto-Speichern komplett neu und würde einen fremden Schlüssel löschen. Felder:
--      stuetz      [{v, ziel, satz}]  Stützpunkte: Verlust v ($, positiv) → Ziel je Tag ($), Satz (€ Hedge je 1.000 $ Ziel); darüber Deckel
--      firmen      [apex, apex100]    Firmen-Schlüssel wie tpVorplanFirmaKey
--      ab_zyklus   2                  nie im ersten Zyklus (Finn)
--      bis         '2x_bester'        Ende: Zyklus-Profit ≥ 2 × bester Tag (Finns Ja vom 01.11.)
--      satz_normal null | Zahl        Stützpunkt 0 für den Satz: null = max(Satz aus der Staffel, erster Stützpunkt-Satz) — so sinkt
--                                     der Satz beim ersten Verlust nie (Befund Konstrukt Abschnitt 7); eine Zahl (z. B. 450) setzt ihn fest
--                                     (Finns Entscheid „fest 450" steht aus)
--      kt          null | Zahl        Kontrakte bei Regel an; null = Firmen-Spanne bleibt (Wert erst auf Finns Wort)
--      aktiv       true               Hauptschalter
-- 2) accounts.wd_zyklus_regel (text): null = automatisch, 'an' = Regel auch ohne Automatik-Bedingungen (außer wd_farm + Apex),
--    'aus' = nie. Setzen über wd_konto_setzen (neuer Parameter p_zyklus_regel), wie wd_tp.
-- 3) wd_konto_setzen: alte 4-Parameter-Fassung wird ENTFERNT und durch die 5-Parameter-Fassung ersetzt — zwei Fassungen nebeneinander
--    kann PostgREST bei rpc('wd_konto_setzen', {p_account, p_wd_farm}) nicht auseinanderhalten („Could not choose the best candidate").
--    Der Riegel vom 02.11.2026 (sql/2026-11-02_wd_riegel_nur_admin.sql, wd_hand_recht) bleibt erhalten: greift, wenn die Funktion da ist;
--    ohne sie (Rückbau eingespielt) wie vorher nur „eingeloggt".
-- Idempotent. Nicht einspielen: Betrieb 1 nach S9-OK, per apply_migration (DDL).

-- 1) Regel-Parameter
alter table public.wd_farmer_regeln add column if not exists zyklus_regel jsonb;
update public.wd_farmer_regeln
   set zyklus_regel = jsonb_build_object(
         'stuetz', jsonb_build_array(jsonb_build_object('v', 2000, 'ziel', 750, 'satz', 400),
                                     jsonb_build_object('v', 4000, 'ziel', 1500, 'satz', 300)),
         'firmen', jsonb_build_array('apex', 'apex100'),
         'ab_zyklus', 2,
         'bis', '2x_bester',
         'satz_normal', null,
         'kt', null,
         'aktiv', true)
 where id = 1 and zyklus_regel is null;

-- 2) Schalter je Konto
alter table public.accounts add column if not exists wd_zyklus_regel text;
alter table public.accounts drop constraint if exists accounts_wd_zyklus_regel_check;
alter table public.accounts add constraint accounts_wd_zyklus_regel_check check (wd_zyklus_regel is null or wd_zyklus_regel in ('an', 'aus'));

-- 3) RPC mit dem neuen Parameter (p_zyklus_regel: null = nicht anfassen, '' = auf automatisch (null) setzen, 'an' / 'aus')
drop function if exists public.wd_konto_setzen(uuid, boolean, numeric, numeric);
create or replace function public.wd_konto_setzen(p_account uuid, p_wd_farm boolean default null, p_tp numeric default null,
                                                  p_sl numeric default null, p_zyklus_regel text default null)
returns boolean language plpgsql security definer set search_path = public as $$
declare v_owner uuid; v_ok boolean := true;
begin
  if auth.uid() is null then raise exception 'nicht angemeldet'; end if;
  select a.user_id into v_owner from public.accounts a where a.id = p_account;
  if v_owner is null then return false; end if;
  -- Riegel vom 02.11.2026, falls eingespielt (sonst wie vorher nur „eingeloggt")
  if to_regprocedure('public.wd_hand_recht(uuid)') is not null then
    execute 'select public.wd_hand_recht($1)' into v_ok using v_owner;
    if not coalesce(v_ok, false) then
      raise exception 'WD-Einstellungen ändert nur die Admin-ID (HT) bzw. der Verwalter (Gruppe)' using errcode = '42501';
    end if;
  end if;
  if p_zyklus_regel is not null and p_zyklus_regel not in ('', 'an', 'aus') then
    raise exception 'wd_zyklus_regel: erlaubt sind '''' (automatisch), ''an'', ''aus''';
  end if;
  update public.accounts
     set wd_farm = coalesce(p_wd_farm, wd_farm),
         wd_tp = case when p_tp is null then wd_tp when p_tp <= 0 then null else p_tp end,
         wd_sl = case when p_sl is null then wd_sl when p_sl <= 0 then null else p_sl end,
         wd_zyklus_regel = case when p_zyklus_regel is null then wd_zyklus_regel when p_zyklus_regel = '' then null else p_zyklus_regel end
   where id = p_account;
  return found;
end $$;
revoke all on function public.wd_konto_setzen(uuid, boolean, numeric, numeric, text) from public;
grant execute on function public.wd_konto_setzen(uuid, boolean, numeric, numeric, text) to authenticated;

-- Probe nach dem Einspielen (nur lesen):
--   select zyklus_regel from public.wd_farmer_regeln where id = 1;
--   select count(*) from pg_proc where proname = 'wd_konto_setzen';   -- muss 1 sein
--   select pg_get_functiondef('public.wd_konto_setzen(uuid,boolean,numeric,numeric,text)'::regprocedure) ilike '%wd_hand_recht%';

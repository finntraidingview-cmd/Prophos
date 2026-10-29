-- VERWALTER BRAUCHT EIGENEN ADMIN-CODE (30.10.2026, PLANER-TAB, Master: „Ein Verwalter darf nie mit '1' entsperrt sein"). Der Tab Planer
-- zeichnet sofort, wenn der Login mit dem Standard-Code (Flag '1', kein eigener Code in admin_zugang) entsperrt ist, und lädt die Übersicht
-- (Verwalter-Erkennung) erst danach. Das ist nur sicher, solange JEDER Verwalter (id_gruppen.verwalter_user_id) einen eigenen Code hat —
-- dann entsperrt er immer mit Flag '2' und wartet im Planer auf die Erkennung. Stand 30.10.2026: 1 Verwalter, hat einen eigenen Code.
-- Dieser Riegel macht daraus eine Regel:
--   (1) id_gruppen: verwalter_user_id setzen/ändern nur auf einen Login mit admin_zugang.code (nicht leer)
--   (2) admin_zugang: Code eines Verwalters nicht leeren und die Zeile nicht löschen
-- Wiederholbar. Rückbau: drop trigger id_gruppen_verwalter_code on public.id_gruppen;
--   drop trigger admin_zugang_verwalter_code on public.admin_zugang; drop function public.prophos_verwalter_code_pruefen();

create or replace function public.prophos_verwalter_code_pruefen()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if tg_table_name = 'id_gruppen' then
    if new.verwalter_user_id is not null
       and not exists (select 1 from public.admin_zugang z where z.user_id = new.verwalter_user_id and coalesce(btrim(z.code), '') <> '') then
      raise exception 'Verwalter braucht einen eigenen Admin-Code (admin_zugang.code) — erst den Code anlegen, dann als Verwalter eintragen'
        using errcode = 'check_violation', hint = 'verwalter_braucht_code';
    end if;
    return new;
  end if;
  -- admin_zugang: Code eines Verwalters bleibt
  if exists (select 1 from public.id_gruppen g where g.verwalter_user_id = old.user_id)
     and (tg_op = 'DELETE' or coalesce(btrim(new.code), '') = '' or new.user_id is distinct from old.user_id) then
    raise exception 'Login ist Verwalter einer Gruppe — eigener Admin-Code bleibt Pflicht (erst Verwalter austragen)'
      using errcode = 'check_violation', hint = 'verwalter_braucht_code';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;

drop trigger if exists id_gruppen_verwalter_code on public.id_gruppen;
create trigger id_gruppen_verwalter_code
  before insert or update of verwalter_user_id on public.id_gruppen
  for each row execute function public.prophos_verwalter_code_pruefen();

drop trigger if exists admin_zugang_verwalter_code on public.admin_zugang;
create trigger admin_zugang_verwalter_code
  before update or delete on public.admin_zugang
  for each row execute function public.prophos_verwalter_code_pruefen();

-- WD-HAKEN VON SELBST (Finn 03.11.2026 ~01:30 Dubai: „Wenn ein Konto zu Winning Days hinzugefügt wird, soll der Haken automatisch gesetzt werden.
-- Für den heutigen Tag soll aber kein Trade mehr gemacht werden, weil da eh schon einer gemacht wurde, aber für die zukünftigen ja.")
-- Anlass: Mike Apex 100k PAAPEX6708370000002 stand auf winning_days mit wd_farm = false — der Farmer nimmt nur Konten mit Haken.
-- Regel: Wechselt accounts.account_type AUF 'winning_days' (Update von einem anderen Typ) oder wird ein Konto gleich als 'winning_days' angelegt,
-- setzt der Trigger wd_farm = true. Jeder Weg ist abgedeckt (Abhaken „→ Winning Days", Knöpfe am Konto, Bearbeiten, Nachfolger-Assistent, Bulk,
-- Admin-Anlage, Ziel-Wache), auch wenn er den Haken selbst nicht mitschickt oder false schickt (Anlage-Wege schreiben wd_farm false, F17).
-- Ein späteres Ausschalten von Hand bleibt: bleibt der Typ winning_days (kein Wechsel), fasst der Trigger wd_farm nicht an.
-- „Heute kein Trade mehr" macht der Farmer selbst (prophos.html wdHeuteGestartet, app.py /admin/wd-plaene heute_gestartet) — nicht die DB.
-- Wiederholbar: create or replace + drop trigger if exists. Keine Daten-Änderung an bestehenden Konten (Mike setzt Finn selbst).

create or replace function public.accounts_wd_farm_bei_wechsel()
returns trigger
language plpgsql
as $$
begin
  if new.account_type = 'winning_days'
     and (tg_op = 'INSERT' or old.account_type is distinct from 'winning_days') then
    new.wd_farm := true;
  end if;
  return new;
end;
$$;

drop trigger if exists accounts_wd_farm_bei_wechsel on public.accounts;
create trigger accounts_wd_farm_bei_wechsel
  before insert or update of account_type on public.accounts
  for each row execute function public.accounts_wd_farm_bei_wechsel();

-- Kontrolle (nur lesen):
-- select tgname, tgenabled from pg_trigger where tgrelid = 'public.accounts'::regclass and tgname = 'accounts_wd_farm_bei_wechsel';
-- select id, name, account_type, wd_farm from public.accounts where account_type = 'winning_days' and wd_farm = false;   -- bleiben, wie sie sind

-- O1b (05.11.2026, Finn: „mach die Add-ons immer in den Namen mit rein, wie bei Jacobs 1 % Rule Acc"): Bestand nachziehen.
-- Konten mit on_demand = true bekommen „ · On Demand" im Namen, falls es fehlt. Stelle wie im Frontend (kontoNameMitAddons):
-- direkt hinter „ · 1% Rule", sonst direkt hinter der Namensregel „<Größe> <External ID> → <Phase>", andere Zusätze bleiben dahinter stehen.
-- Idempotent (nur Konten ohne „On Demand" im Namen). Stand beim Schreiben: 3 Konten betroffen.
update public.accounts
set name = case
    when name ~* ' · 1\s*%\s*-?\s*rule' then regexp_replace(name, '( · 1\s*%\s*-?\s*rule)', '\1 · On Demand', 'i')
    when position(' · ' in name) > 0 then regexp_replace(name, ' · ', ' · On Demand · ')
    else name || ' · On Demand'
  end
where on_demand = true
  and name !~* 'on[ -]*demand';

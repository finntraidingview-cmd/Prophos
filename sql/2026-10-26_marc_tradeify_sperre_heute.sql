-- 2026-10-26 (~16:12 Dubai): Marc × Tradeify für den Rest des Tages gesperrt.
-- Anlass: Finn ist bei Marc gerade in einem manuellen Trade („bei Mark Tradeify: keine Challenges für heute").
-- Der Gegenrichtungs-Riegel kennt den Hand-Trade nicht, also darf heute kein Tradeify-Trade für Marc mehr laufen.
-- Stand beim Setzen: 1 Plan geplant (34f16a7c, …2967999, Start 12:25 UTC) → entfernt; bb13f398 completed, 555fe35b review.
-- Weg wie 2026-10-23_marco_topstep_sperre_heute.sql: accounts.auto_planer = false an allen 14 Tradeify-Konten
-- (13 Challenges + 1 Funded, der Vollständigkeit halber). Idempotent.

update public.accounts
   set auto_planer = false, updated_at = now()
 where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'          -- Marc
   and firm = 'Tradeify';

-- Geplanten Plan entfernen wie der 🗑-Knopf im Planer (trade_plans kennt kein 'cancelled'; nur solange noch 'planned').
delete from public.trade_plans
 where id = '34f16a7c-b44f-4275-98f9-4ecdcb0ee1b9'
   and status = 'planned';

-- Lesen:
-- select name, auto_planer from public.accounts where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and firm = 'Tradeify';

-- ENDE (morgen 27.10.2026, wenn der Hand-Trade zu ist — erst dann ausführen):
-- update public.accounts set auto_planer = true, updated_at = now()
--  where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and firm = 'Tradeify';

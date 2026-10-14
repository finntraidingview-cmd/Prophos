-- WINNING-DAY-STAND VON HAND (Finn 14.10.2026 ~23:45 Dubai, Accounts-Liste: Chris, Topstep EXPRESS-V2-679005-57119155 → Winning Days,
-- Anzeige „0/5 Winning Days" — Finn: „dem bitte 3/5 geben"). Prophos zählt Winning Days selbst (goal_done_offset, +1 je Good Day
-- über 250 $ bzw. Haken beim Abhaken, höchstens einmal je Berlin-Tag); die drei Tage waren bei Topstep schon gezählt, bei uns nicht.
-- Angewendet 14.10.2026 ~19:45 UTC direkt gegen die DB (Konto 9281c481-…).
update public.accounts
   set goal_done_offset = 3, goal_kind = 'winning_days', goal_manual = true, goal_target = coalesce(nullif(goal_target, 0), 5)
 where external_id = 'EXPRESS-V2-679005-57119155' and account_type = 'winning_days';

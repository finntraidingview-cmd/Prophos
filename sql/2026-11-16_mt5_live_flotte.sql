-- SB2b (16.11.2026, Supabase-Rechnung 232 $ für 16.10.–16.11., Befund SB1): ~75 % des Egress kam aus mt5_live. Die PC-Tabs laden
-- an Handelstagen ~65.000-mal am Tag alle frischen Flotten-Zeilen mit select=* (mt5FleetRenderTick alle 5 s, hedgeCloudRowsNachladen,
-- firmLiveRichtungen), je Zeile ~10 KB, fast alles in status. Drei Schlüssel darin liest keiner dieser Leser:
--   panel_lauf   (~1,7 KB, Frontend liest ihn nirgends, nur der Flotten-Push schreibt ihn)
--   mt5_update   (~0,6 KB, nur Admin-PC-Tabelle, die kommt von Railway /admin/pc-stand)
--   kurs_bruecke (~0,4 KB, nur die Brücken-Diagnose, eigene Abfrage direkt auf mt5_live)
-- Diese Sicht liefert dieselben Zeilen und Spalten ohne die drei Schlüssel. hedge_solo_zu bleibt voll (Ring der letzten 20):
-- je Copier bis zu 8 Abschlüsse in 6 h gemessen, ein kürzerer Ring könnte am Mac einen geschlossenen Hedge verpassen.
-- security_invoker: die RLS „mt5_live read“ (Flotten-privat vs. HT) gilt unverändert für den Aufrufer.
-- Schreiber (Flotten-Push, Copier, Railway) und alle anderen Leser bleiben auf mt5_live. Idempotent.

create or replace view public.mt5_live_flotte
with (security_invoker = true)
as
select id, pc_name, config_file, instance, master_login, hedge_login, alive,
       status - array['panel_lauf', 'mt5_update', 'kurs_bruecke'] as status,
       updated_at
from public.mt5_live;

comment on view public.mt5_live_flotte is
  'Schlanke Lese-Sicht für die Flotten-Abfragen der PC-Tabs (SB2b 16.11.2026): mt5_live ohne status.panel_lauf/mt5_update/kurs_bruecke. RLS von mt5_live gilt (security_invoker).';

revoke all on public.mt5_live_flotte from public, anon;
grant select on public.mt5_live_flotte to authenticated;

notify pgrst, 'reload schema';

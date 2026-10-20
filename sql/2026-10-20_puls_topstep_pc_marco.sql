-- 2026-10-20: Marco-PC in die Topstep-CDP-Liste (Master-Auftrag TOPSTEP-FALSCHER-BROWSER-MARCO, S3-Befund).
-- Befund: pc-t8wg97 steht seit 14.10. in puls_augen_cdp (Orbit läuft dort über das Puls-Chrome), aber NICHT in puls_topstep_pcs.
-- GET /puls-regel/pc-t8wg97 liefert deshalb tsx 'uia' (app.py puls_regel_lesen: 'cdp' genau dann, wenn pc in puls_topstep_pcs),
-- und der Topstep-Puls nimmt den alten UIA-Weg im normalen Chrome (order_bot.py tsx_weg_lauf → modus_tsxlesen weg 'uia',
-- _tsx_tab_holen: gemerktes „Puls-Fenster" = Marcos Haupt-Chrome). Heute 00:36–08:15 UTC 12 Login-Fehlstarts dort.
-- Kein Code-Fehler — nur der Schalter fehlt. Wirkt beim nächsten Lauf (Bot fragt vor jedem Topstep-Lauf, Railway-Cache 10 s),
-- kein Neustart nötig. Danach EINMAL von Hand: TopstepX im Puls-Chrome anmelden (Passwort speichern, Chrome-Autofill — der Puls
-- tippt nie, er drückt nur „PLATFORM LOGIN" mit Autofill-Beweis), wie auf den anderen vier Topstep-PCs.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(puls_topstep_pcs, 'pc-t8wg97'), updated_at = now()
 where id = 1 and not ('pc-t8wg97' = any(puls_topstep_pcs));

-- Lesen:
-- select puls_topstep, puls_topstep_pcs, puls_augen_cdp from public.wd_farmer_regeln where id = 1;

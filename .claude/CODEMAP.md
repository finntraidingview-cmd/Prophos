# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (75741 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 49–7399 | 7351 |
| HTML-Markup (Views + Modals) | 7400–13899 | 6500 |
| **JS-Modul** (ein `<script type="module">`) | **13900–73590** | **59691** |
| Rest (CSS-/JS-Nachtrag) | 73591–75741 | 2151 |

## prophos.html — JS-Sektionen (13900–73590)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 13944–13973 | 30 | VIEW SWITCHER |
| 13974–14011 | 38 | BOOT |
| 14012–14354 | 343 | USER HYDRATION |
| 14355–14374 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 14375–14400 | 26 | BANNERS |
| 14401–14423 | 23 | LOGIN |
| 14424–14456 | 33 | SIGNUP |
| 14457–14481 | 25 | RESET |
| 14482–14501 | 20 | LOGOUT |
| 14502–14517 | 16 | USER DROPDOWN |
| 14518–19966 | 5449 | DASHBOARD TABS |
| 19967–20020 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 20021–20330 | 310 | MOBILE SIDEBAR |
| 20331–20338 | 8 | DASHBOARD MOUNT |
| 20339–20607 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 20608–20901 | 294 | DUPLIKUM CONNECTION |
| 20902–21166 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 21167–21650 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 21651–22046 | 396 | DUPLIKUM LINKING (lokal) |
| 22047–24103 | 2057 | ENDE MT5-COPIER LINKING |
| 24104–25567 | 1464 | ENDE MT5-ROUTE |
| 25568–28591 | 3024 | ENDE ORBIT V2 |
| 28592–31025 | 2434 | ENDE FUSION-GEGENHEDGE |
| 31026–33336 | 2311 | ENDE MARKT LIVE |
| 33337–33467 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 33468–33917 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 33918–35862 | 1945 | DUPLIKUM AUTO-REFRESH |
| 35863–35952 | 90 | TRADE-COMPLETE: Status-Optionen |
| 35953–36362 | 410 | NACHFOLGER-WIZARD |
| 36363–36370 | 8 | ARCHIV-FILTER |
| 36371–39032 | 2662 | ACCOUNTS — SUPABASE CRUD |
| 39033–39940 | 908 | BULK ADD ACCOUNTS |
| 39941–39944 | 4 | END BULK ADD |
| 39945–40762 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 40763–40822 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 40823–41518 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 41519–41666 | 148 | LOT RECHNER |
| 41667–64341 | 22675 | TRADE PLANS |
| 64342–65665 | 1324 | FINANZEN |
| 65666–73590 | 7925 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 24248–25415 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 25416–31619 | P&L NACH DEM TRADE — DREI QUELLEN |
| 31620–31932 | SPANNE |
| 31933–36911 | WARTET |
| 36912–42823 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 42824–42881 | GEPLANTE TRADES FÜR POLAR |
| 42882 | ENDE GEPLANTE TRADES FÜR POLAR |
| 44957–47250 | ECHO V2 — Trade-Start ohne Hedge |
| 47251–48493 | REMOTE-TRADE-SIGNALE |
| 48494–49161 | AUTO-START-WARTESCHLANGE |
| 49162–49586 | V2 SCHLIESSEN |
| 49587 | ENDE V2 SCHLIESSEN |
| 50346 | ENDE REMOTE-TRADE-SIGNALE |
| 50348–50620 | BENACHRICHTIGUNGEN AUFS HANDY |
| 50621 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 50623–50832 | AUTO-CLOSE VOR MARKET CLOSE |
| 50833–51547 | GEPLANTE STARTZEIT |
| 51548–51924 | RICHTUNG AM START |
| 51925–52176 | START-FEHLER & NEU EINPLANEN |
| 52177 | ENDE START-FEHLER |
| 52615 | ENDE GEPLANTE STARTZEIT |
| 52617–53391 | AUTO-PLANER |
| 53392 | ENDE AUTO-PLANER |
| 53394–55160 | TRADE-PLANER-SEITE |
| 55161–56230 | HEUTE BEENDET |
| 56231 | ENDE TRADE-PLANER-SEITE |
| 56239 | ENDE AUTO-CLOSE |
| 59278–59316 | CHALLENGES MIT HEDGE |
| 59317–59879 | FUTURES VORPLANEN |
| 59880 | ENDE FUTURES VORPLANEN |
| 59882–62214 | WINNING-DAY-FARMER |
| 62215 | ENDE WINNING-DAY-FARMER |
| 62217–62335 | WD-ANBAU |
| 62336 | ENDE WD-ANBAU |
| 65715–66040 | MAIL-REITER |
| 66041 | ENDE MAIL-REITER |
| 66043–71496 | ADMIN → MAIL |
| 71497–71934 | ADMIN „TRADE-PLANER" |
| 71935–72046 | ID-DETAIL |
| 72047–72279 | GRUPPEN-PLANER |
| 72280 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 34112 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 34621 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 35108 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 35530 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 35635 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 66254 | SUPABASE-SYNC für localStorage-Daten |
| 66477 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 66960 | FX-Kurs USD/EUR |
| 67128 | JOURNAL — Tägliche Trading-Notizen |
| 67422 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 67786 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 68048 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (7400–13899)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 7928 | view: **overview** |
| 8041 | view: **accounts** |
| 8396 | modal: linkTopstepModal |
| 8437 | view: **topstep** |
| 8534 | view: **calc** |
| 8662 | view: **trades** |
| 8851 | modal: tpVorplanModal |
| 8945 | modal: tplBestModal |
| 8961 | modal: apKontoModal |
| 8972 | modal: handModal |
| 8981 | modal: apProbeModal |
| 9003 | modal: tpOrderModal |
| 9085 | modal: tradePlanModal |
| 9488 | modal: polarModal |
| 9582 | modal: polarCheckModal |
| 9616 | modal: tradeCompleteModal |
| 9741 | modal: successorModal |
| 9885 | modal: blownSummaryModal |
| 9922 | modal: tpPreflightModal |
| 9954 | modal: vcModal |
| 9990 | view: **risk** |
| 10008 | view: **advisor** |
| 10121 | modal: advisor-firm-modal |
| 10184 | modal: advisor-kb-modal |
| 10198 | modal: advisor-memory-modal |
| 10212 | modal: advisor-extract-modal |
| 10226 | view: **payouts** |
| 10475 | modal: finModal |
| 10571 | modal: finReceiveModal |
| 10602 | modal: finSettleModal |
| 10650 | view: **analytics** |
| 10668 | view: **journal** |
| 10756 | view: **account-detail** |
| 10805 | view: **livetrades** |
| 10838 | modal: linkDupModal |
| 10879 | modal: linkMt5Modal |
| 10920 | view: **managed** |
| 11011 | modal: mgSettleModal |
| 11058 | view: **notes** |
| 11078 | view: **mail** |
| 11109 | view: **news** |
| 11149 | view: **propbaum** |
| 11180 | view: **tplaner** |
| 11202 | view: **vorrat** |
| 11222 | view: **wdlive** |
| 11255 | view: **firmen** |
| 11301 | view: **markt** |
| 11371 | view: **mt5copier** |
| 11450 | view: **echoplus** |
| 11493 | modal: mtcAddModal |
| 11547 | view: **kasse** |
| 12967 | modal: walKommModal |
| 13013 | view: **settings** |
| 13172 | modal: customFirmModal |
| 13322 | modal: mwdErledigtModal |
| 13385 | modal: addAccountModal |
| 13716 | modal: credModal |
| 13733 | modal: bulkAddModal |

## app.py — Routen (29920 Zeilen)

| Zeile | Route |
|---|---|
| 47 | `"/version", methods=["GET"]` |
| 71 | `"/news/calendar", methods=["GET", "OPTIONS"]` |
| 172 | `"/markt/futures", methods=["GET", "OPTIONS"]` |
| 349 | `"/"` |
| 393 | `"/mt5-copier/VERSION", methods=["GET"]` |
| 435 | `"/api/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 449 | `"/ma/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 482 | `"/copier/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 566 | `"/local/restart-stack", methods=["POST", "OPTIONS"]` |
| 632 | `"/duplikum/connect", methods=["POST","OPTIONS"]` |
| 737 | `"/duplikum/session", methods=["GET", "OPTIONS"]` |
| 777 | `"/duplikum/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 934 | `"/duplikum/refresh", methods=["POST","OPTIONS"]` |
| 972 | `"/duplikum/disconnect", methods=["POST","OPTIONS"]` |
| 1188 | `"/mirror/start", methods=["POST","OPTIONS"]` |
| 1196 | `"/mirror/stop", methods=["POST","OPTIONS"]` |
| 1211 | `"/mirror/status", methods=["GET"]` |
| 1310 | `"/mirror/diagnose", methods=["POST", "OPTIONS", "GET"]` |
| 2634 | `"/debug/account", methods=["POST","OPTIONS"]` |
| 3837 | `"/alarm/heimweg", methods=["POST", "OPTIONS"]` |
| 3875 | `"/alarm/stand", methods=["GET", "POST", "OPTIONS"]` |
| 3900 | `"/push/vapid-public", methods=["GET", "OPTIONS"]` |
| 3914 | `"/push/subscribe", methods=["POST", "OPTIONS"]` |
| 3946 | `"/push/unsubscribe", methods=["POST", "OPTIONS"]` |
| 3970 | `"/push/geraete", methods=["GET", "OPTIONS"]` |
| 3988 | `"/push/send", methods=["POST", "OPTIONS"]` |
| 4013 | `"/konto-weg/melden", methods=["POST", "OPTIONS"]` |
| 4058 | `"/sw.js", methods=["GET"]` |
| 7190 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7486 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7673 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7813 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 8008 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 8105 | `"/admin/muster-portfolio", methods=["GET", "OPTIONS"]` |
| 10155 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 10184 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10563 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10583 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10644 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10660 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10790 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11639 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12618 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 13055 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 13107 | `"/pc-namen", methods=["GET", "OPTIONS"]` |
| 13255 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 13365 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 14016 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 14070 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 14104 | `"/health", methods=["GET", "OPTIONS"]` |
| 14450 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 15097 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 15184 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15243 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 15377 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 15420 | `"/code/stand", methods=["GET"]` |
| 15668 | `"/admin/puls-heim", methods=["GET", "OPTIONS"]` |
| 15688 | `"/richtung/frei", methods=["POST"]` |
| 15793 | `"/mail/eingang", methods=["POST"]` |
| 15959 | `"/admin/mail", methods=["GET", "PATCH", "OPTIONS"]` |
| 16022 | `"/admin/mail/<int:mid>", methods=["GET", "OPTIONS"]` |
| 16042 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 16096 | `"/code/tab-stand/<pc>", methods=["GET"]` |
| 16136 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 16219 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 16302 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 16431 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 16542 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16639 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 16709 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16728 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 18863 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 18996 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19729 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 26072 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 26123 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 26143 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 26288 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 26657 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 26896 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 26931 | `"/admin/auto-plan/waage-start", methods=["POST", "OPTIONS"]` |
| 26977 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 28119 | `"/admin/ziel-wache-jetzt", methods=["POST", "OPTIONS"]` |
| 29030 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 29035 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 29040 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 29045 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 29437 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 29445 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 29460 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 29487 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 29506 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |
| 29627 | `"/admin/kunden-zahlungen", methods=["GET", "OPTIONS"]` |
| 29635 | `"/admin/kunden-zahlungen/buchen", methods=["POST", "OPTIONS"]` |
| 29659 | `"/admin/kunden-zahlungen/aktiv", methods=["POST", "OPTIONS"]` |

## app.py — Sektionen

| Zeile | Sektion |
|---|---|
| 21 | signalrcore-Hotfixes (21.07.2026, beide im Live-Test nachgewiesen) |
| 59 | Forex-Factory News-Kalender (öffentlicher Wochen-Feed, gecacht) |
| 108 | Futures-Kurse NQ / MNQ (30.08.2026, Finns Wunsch „NQ-Live-Stand ablesen") |
| 283 | Kurz-Cache + Single-Flight für Duplikum-LESE-Endpoints (22.07.2026) |
| 384 | Frontend-Version für den Build-Wächter (25.09.2026, Koordination: PC-Tabs liefen tagelang auf altem Stand — Mikes |
| 434 | TopstepX Proxy |
| 448 | MetaApi Proxy |
| 473 | MT5-Copier Panel-Proxy (Etappe 3, 15.08.2026) |
| 539 | Stack-Neustart per Knopf (15.08.2026, Finns Wunsch) |
| 631 | Duplikium Connect (Basic Auth → Token) |
| 729 | Duplikium Session-Handout (25.08.2026) |
| 776 | Duplikium Generic Proxy |
| 981 | Token Refresh |
| 1042 | Sessions überleben einen Backend-Neustart (17.09.2026) |
| 1187 | Mirror Control |
| 1234 | Mirror-Diagnose: Wer killt den Stream? (08.09.2026) |
| 1337 | Mirror Logic (Polling) TSX → MT5 |
| 1468 | TSX → MT5 Mirror, Echtzeit (SignalR statt Polling, 20.07.2026) |
| 2155 | NOTFALL-SL/TP für den Topstep-Mirror (17.09.2026) |
| 2407 | MT5 → TopstepX Mirror |
| 2721 | Duplikum-Rate-Budget (06.08.2026) |
| 3150 | Kurz-Caches für Login-Prüfung & Co. (01.10.2026, SUPABASE-DIÄT B) |
| 3264 | ADMIN-GRUPPEN (08.10.2026, Finn ~22:45 Dubai: „Emin bekommt seine Freunde als eigene IDs bei sich unter Admin … Ich sage in |
| 4678 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 5654 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10948 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 11110 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 14097 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 14237 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 15391 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 16560 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 16654 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 17983 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 18689 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 19906 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 22842 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 29524 | WIEDERKEHRENDE BUCHUNGEN (14.10.2026, Finn: „unter Finanzen manuell einbuchen und recurring auswählen — jeden Monat am 2. zieht |
| 29715 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 29750 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (75741 Zeilen) und app.py._

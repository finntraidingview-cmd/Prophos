# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (75701 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 49–7399 | 7351 |
| HTML-Markup (Views + Modals) | 7400–13899 | 6500 |
| **JS-Modul** (ein `<script type="module">`) | **13900–73550** | **59651** |
| Rest (CSS-/JS-Nachtrag) | 73551–75701 | 2151 |

## prophos.html — JS-Sektionen (13900–73550)

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
| 22047–24102 | 2056 | ENDE MT5-COPIER LINKING |
| 24103–25566 | 1464 | ENDE MT5-ROUTE |
| 25567–28590 | 3024 | ENDE ORBIT V2 |
| 28591–31024 | 2434 | ENDE FUSION-GEGENHEDGE |
| 31025–33335 | 2311 | ENDE MARKT LIVE |
| 33336–33466 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 33467–33916 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 33917–35861 | 1945 | DUPLIKUM AUTO-REFRESH |
| 35862–35951 | 90 | TRADE-COMPLETE: Status-Optionen |
| 35952–36361 | 410 | NACHFOLGER-WIZARD |
| 36362–36369 | 8 | ARCHIV-FILTER |
| 36370–39031 | 2662 | ACCOUNTS — SUPABASE CRUD |
| 39032–39902 | 871 | BULK ADD ACCOUNTS |
| 39903–39906 | 4 | END BULK ADD |
| 39907–40724 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 40725–40784 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 40785–41480 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 41481–41628 | 148 | LOT RECHNER |
| 41629–64301 | 22673 | TRADE PLANS |
| 64302–65625 | 1324 | FINANZEN |
| 65626–73550 | 7925 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 24247–25414 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 25415–31618 | P&L NACH DEM TRADE — DREI QUELLEN |
| 31619–31931 | SPANNE |
| 31932–36910 | WARTET |
| 36911–42783 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 42784–42841 | GEPLANTE TRADES FÜR POLAR |
| 42842 | ENDE GEPLANTE TRADES FÜR POLAR |
| 44917–47210 | ECHO V2 — Trade-Start ohne Hedge |
| 47211–48453 | REMOTE-TRADE-SIGNALE |
| 48454–49121 | AUTO-START-WARTESCHLANGE |
| 49122–49546 | V2 SCHLIESSEN |
| 49547 | ENDE V2 SCHLIESSEN |
| 50306 | ENDE REMOTE-TRADE-SIGNALE |
| 50308–50580 | BENACHRICHTIGUNGEN AUFS HANDY |
| 50581 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 50583–50792 | AUTO-CLOSE VOR MARKET CLOSE |
| 50793–51507 | GEPLANTE STARTZEIT |
| 51508–51884 | RICHTUNG AM START |
| 51885–52136 | START-FEHLER & NEU EINPLANEN |
| 52137 | ENDE START-FEHLER |
| 52575 | ENDE GEPLANTE STARTZEIT |
| 52577–53351 | AUTO-PLANER |
| 53352 | ENDE AUTO-PLANER |
| 53354–55120 | TRADE-PLANER-SEITE |
| 55121–56190 | HEUTE BEENDET |
| 56191 | ENDE TRADE-PLANER-SEITE |
| 56199 | ENDE AUTO-CLOSE |
| 59238–59276 | CHALLENGES MIT HEDGE |
| 59277–59839 | FUTURES VORPLANEN |
| 59840 | ENDE FUTURES VORPLANEN |
| 59842–62174 | WINNING-DAY-FARMER |
| 62175 | ENDE WINNING-DAY-FARMER |
| 62177–62295 | WD-ANBAU |
| 62296 | ENDE WD-ANBAU |
| 65675–66000 | MAIL-REITER |
| 66001 | ENDE MAIL-REITER |
| 66003–71456 | ADMIN → MAIL |
| 71457–71894 | ADMIN „TRADE-PLANER" |
| 71895–72006 | ID-DETAIL |
| 72007–72239 | GRUPPEN-PLANER |
| 72240 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 34111 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 34620 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 35107 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 35529 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 35634 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 66214 | SUPABASE-SYNC für localStorage-Daten |
| 66437 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 66920 | FX-Kurs USD/EUR |
| 67088 | JOURNAL — Tägliche Trading-Notizen |
| 67382 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 67746 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 68008 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

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

## app.py — Routen (29918 Zeilen)

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
| 7188 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7484 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7671 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7811 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 8006 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 8103 | `"/admin/muster-portfolio", methods=["GET", "OPTIONS"]` |
| 10153 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 10182 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10561 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10581 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10642 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10658 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10788 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11637 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12616 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 13053 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 13105 | `"/pc-namen", methods=["GET", "OPTIONS"]` |
| 13253 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 13363 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 14014 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 14068 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 14102 | `"/health", methods=["GET", "OPTIONS"]` |
| 14448 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 15095 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 15182 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15241 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 15375 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 15418 | `"/code/stand", methods=["GET"]` |
| 15666 | `"/admin/puls-heim", methods=["GET", "OPTIONS"]` |
| 15686 | `"/richtung/frei", methods=["POST"]` |
| 15791 | `"/mail/eingang", methods=["POST"]` |
| 15957 | `"/admin/mail", methods=["GET", "PATCH", "OPTIONS"]` |
| 16020 | `"/admin/mail/<int:mid>", methods=["GET", "OPTIONS"]` |
| 16040 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 16094 | `"/code/tab-stand/<pc>", methods=["GET"]` |
| 16134 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 16217 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 16300 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 16429 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 16540 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16637 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 16707 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16726 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 18861 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 18994 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19727 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 26070 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 26121 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 26141 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 26286 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 26655 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 26894 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 26929 | `"/admin/auto-plan/waage-start", methods=["POST", "OPTIONS"]` |
| 26975 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 28117 | `"/admin/ziel-wache-jetzt", methods=["POST", "OPTIONS"]` |
| 29028 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 29033 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 29038 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 29043 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 29435 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 29443 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 29458 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 29485 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 29504 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |
| 29625 | `"/admin/kunden-zahlungen", methods=["GET", "OPTIONS"]` |
| 29633 | `"/admin/kunden-zahlungen/buchen", methods=["POST", "OPTIONS"]` |
| 29657 | `"/admin/kunden-zahlungen/aktiv", methods=["POST", "OPTIONS"]` |

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
| 5652 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10946 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 11108 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 14095 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 14235 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 15389 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 16558 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 16652 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 17981 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 18687 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 19904 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 22840 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 29522 | WIEDERKEHRENDE BUCHUNGEN (14.10.2026, Finn: „unter Finanzen manuell einbuchen und recurring auswählen — jeden Monat am 2. zieht |
| 29713 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 29748 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (75701 Zeilen) und app.py._

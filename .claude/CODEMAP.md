# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (64239 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 25–6355 | 6331 |
| HTML-Markup (Views + Modals) | 6356–12362 | 6007 |
| **JS-Modul** (ein `<script type="module">`) | **12363–63943** | **51581** |
| Rest (CSS-/JS-Nachtrag) | 63944–64239 | 296 |

## prophos.html — JS-Sektionen (12363–63943)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 12398–12427 | 30 | VIEW SWITCHER |
| 12428–12465 | 38 | BOOT |
| 12466–12762 | 297 | USER HYDRATION |
| 12763–12782 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 12783–12808 | 26 | BANNERS |
| 12809–12831 | 23 | LOGIN |
| 12832–12864 | 33 | SIGNUP |
| 12865–12889 | 25 | RESET |
| 12890–12909 | 20 | LOGOUT |
| 12910–12925 | 16 | USER DROPDOWN |
| 12926–17946 | 5021 | DASHBOARD TABS |
| 17947–18000 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 18001–18298 | 298 | MOBILE SIDEBAR |
| 18299–18306 | 8 | DASHBOARD MOUNT |
| 18307–18575 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 18576–18869 | 294 | DUPLIKUM CONNECTION |
| 18870–19134 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 19135–19618 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 19619–20014 | 396 | DUPLIKUM LINKING (lokal) |
| 20015–22022 | 2008 | ENDE MT5-COPIER LINKING |
| 22023–23172 | 1150 | ENDE MT5-ROUTE |
| 23173–25723 | 2551 | ENDE ORBIT V2 |
| 25724–27927 | 2204 | ENDE FUSION-GEGENHEDGE |
| 27928–29251 | 1324 | ENDE MARKT LIVE |
| 29252–29382 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 29383–29832 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 29833–31696 | 1864 | DUPLIKUM AUTO-REFRESH |
| 31697–31783 | 87 | TRADE-COMPLETE: Status-Optionen |
| 31784–32098 | 315 | NACHFOLGER-WIZARD |
| 32099–32106 | 8 | ARCHIV-FILTER |
| 32107–34522 | 2416 | ACCOUNTS — SUPABASE CRUD |
| 34523–35275 | 753 | BULK ADD ACCOUNTS |
| 35276–35279 | 4 | END BULK ADD |
| 35280–36097 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 36098–36157 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 36158–36853 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 36854–37001 | 148 | LOT RECHNER |
| 37002–55731 | 18730 | TRADE PLANS |
| 55732–56977 | 1246 | FINANZEN |
| 56978–63943 | 6966 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 23022–28358 | P&L NACH DEM TRADE — DREI QUELLEN |
| 28359–28533 | SPANNE |
| 28534–32629 | WARTET |
| 32630–39820 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 39821–41948 | ECHO V2 — Trade-Start ohne Hedge |
| 41949–42990 | REMOTE-TRADE-SIGNALE |
| 42991–43623 | AUTO-START-WARTESCHLANGE |
| 43624–44037 | V2 SCHLIESSEN |
| 44038 | ENDE V2 SCHLIESSEN |
| 44754 | ENDE REMOTE-TRADE-SIGNALE |
| 44756–45000 | BENACHRICHTIGUNGEN AUFS HANDY |
| 45001 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 45003–45207 | AUTO-CLOSE VOR MARKET CLOSE |
| 45208–45882 | GEPLANTE STARTZEIT |
| 45883–45979 | RICHTUNG AM START |
| 45980–46127 | START-FEHLER & NEU EINPLANEN |
| 46128 | ENDE START-FEHLER |
| 46387 | ENDE GEPLANTE STARTZEIT |
| 46389–47142 | AUTO-PLANER |
| 47143 | ENDE AUTO-PLANER |
| 47145–48508 | TRADE-PLANER-SEITE |
| 48509–49482 | HEUTE BEENDET |
| 49483 | ENDE TRADE-PLANER-SEITE |
| 49491 | ENDE AUTO-CLOSE |
| 51326–51842 | FUTURES VORPLANEN |
| 51843 | ENDE FUTURES VORPLANEN |
| 51845–53981 | WINNING-DAY-FARMER |
| 53982 | ENDE WINNING-DAY-FARMER |
| 53984–54100 | WD-ANBAU |
| 54101 | ENDE WD-ANBAU |
| 62191–62571 | ADMIN „TRADE-PLANER" |
| 62572–62840 | ID-DETAIL |
| 62841 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 30027 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 30536 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 31023 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 31445 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 31550 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 57090 | SUPABASE-SYNC für localStorage-Daten |
| 57313 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 57796 | FX-Kurs USD/EUR |
| 57964 | JOURNAL — Tägliche Trading-Notizen |
| 58258 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 58622 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 58884 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (6356–12362)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 6862 | view: **overview** |
| 6975 | view: **accounts** |
| 7308 | modal: linkTopstepModal |
| 7349 | view: **topstep** |
| 7446 | view: **calc** |
| 7574 | view: **trades** |
| 7743 | modal: tpVorplanModal |
| 7835 | modal: tplBestModal |
| 7851 | modal: apKontoModal |
| 7860 | modal: apProbeModal |
| 7882 | modal: tpOrderModal |
| 7964 | modal: tradePlanModal |
| 8353 | modal: tradeCompleteModal |
| 8461 | modal: successorModal |
| 8605 | modal: blownSummaryModal |
| 8642 | modal: tpPreflightModal |
| 8674 | modal: vcModal |
| 8710 | view: **risk** |
| 8728 | view: **advisor** |
| 8841 | modal: advisor-firm-modal |
| 8904 | modal: advisor-kb-modal |
| 8918 | modal: advisor-memory-modal |
| 8932 | modal: advisor-extract-modal |
| 8946 | view: **payouts** |
| 9185 | modal: finModal |
| 9272 | modal: finReceiveModal |
| 9303 | modal: finSettleModal |
| 9351 | view: **analytics** |
| 9369 | view: **journal** |
| 9457 | view: **account-detail** |
| 9506 | view: **livetrades** |
| 9539 | modal: linkDupModal |
| 9580 | modal: linkMt5Modal |
| 9621 | view: **managed** |
| 9712 | modal: mgSettleModal |
| 9759 | view: **notes** |
| 9779 | view: **news** |
| 9819 | view: **propbaum** |
| 9850 | view: **tplaner** |
| 9872 | view: **vorrat** |
| 9892 | view: **wdlive** |
| 9923 | view: **firmen** |
| 9969 | view: **markt** |
| 10039 | view: **mt5copier** |
| 10118 | view: **echoplus** |
| 10161 | modal: mtcAddModal |
| 10215 | view: **kasse** |
| 11490 | modal: walKommModal |
| 11536 | view: **settings** |
| 11667 | modal: customFirmModal |
| 11817 | modal: mwdErledigtModal |
| 11877 | modal: addAccountModal |
| 12184 | modal: credModal |
| 12201 | modal: bulkAddModal |

## app.py — Routen (21675 Zeilen)

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
| 3342 | `"/push/vapid-public", methods=["GET", "OPTIONS"]` |
| 3356 | `"/push/subscribe", methods=["POST", "OPTIONS"]` |
| 3388 | `"/push/unsubscribe", methods=["POST", "OPTIONS"]` |
| 3412 | `"/push/geraete", methods=["GET", "OPTIONS"]` |
| 3430 | `"/push/send", methods=["POST", "OPTIONS"]` |
| 3447 | `"/sw.js", methods=["GET"]` |
| 6303 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 6599 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 6786 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 6924 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7119 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 9071 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 9100 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 9479 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 9499 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 9560 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 9576 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 9705 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 10508 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 11367 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 11739 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 11759 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 12377 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 12415 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 12449 | `"/health", methods=["GET", "OPTIONS"]` |
| 12795 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 13440 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 13527 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 13586 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 13720 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 13763 | `"/code/stand", methods=["GET"]` |
| 13781 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 13806 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 13889 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 13971 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 14086 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 14197 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14294 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 14364 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14383 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15485 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 15616 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19900 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 19931 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 19951 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 20376 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 20512 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 20547 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 21394 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 21399 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 21404 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 21409 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |

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
| 3091 | Kurz-Caches für Login-Prüfung & Co. (01.10.2026, SUPABASE-DIÄT B) |
| 4067 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 4968 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 9863 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 10000 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 12442 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 12582 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 13734 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 14215 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 14309 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 14852 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 15387 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 16231 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 17488 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 21476 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 21511 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (64239 Zeilen) und app.py._

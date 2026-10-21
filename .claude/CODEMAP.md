# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (74300 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 49–7279 | 7231 |
| HTML-Markup (Views + Modals) | 7280–13736 | 6457 |
| **JS-Modul** (ein `<script type="module">`) | **13737–72149** | **58413** |
| Rest (CSS-/JS-Nachtrag) | 72150–74300 | 2151 |

## prophos.html — JS-Sektionen (13737–72149)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 13772–13801 | 30 | VIEW SWITCHER |
| 13802–13839 | 38 | BOOT |
| 13840–14181 | 342 | USER HYDRATION |
| 14182–14201 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 14202–14227 | 26 | BANNERS |
| 14228–14250 | 23 | LOGIN |
| 14251–14283 | 33 | SIGNUP |
| 14284–14308 | 25 | RESET |
| 14309–14328 | 20 | LOGOUT |
| 14329–14344 | 16 | USER DROPDOWN |
| 14345–19764 | 5420 | DASHBOARD TABS |
| 19765–19818 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 19819–20128 | 310 | MOBILE SIDEBAR |
| 20129–20136 | 8 | DASHBOARD MOUNT |
| 20137–20405 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 20406–20699 | 294 | DUPLIKUM CONNECTION |
| 20700–20964 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 20965–21448 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 21449–21844 | 396 | DUPLIKUM LINKING (lokal) |
| 21845–23899 | 2055 | ENDE MT5-COPIER LINKING |
| 23900–25207 | 1308 | ENDE MT5-ROUTE |
| 25208–28101 | 2894 | ENDE ORBIT V2 |
| 28102–30460 | 2359 | ENDE FUSION-GEGENHEDGE |
| 30461–32654 | 2194 | ENDE MARKT LIVE |
| 32655–32785 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 32786–33235 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 33236–35180 | 1945 | DUPLIKUM AUTO-REFRESH |
| 35181–35270 | 90 | TRADE-COMPLETE: Status-Optionen |
| 35271–35638 | 368 | NACHFOLGER-WIZARD |
| 35639–35646 | 8 | ARCHIV-FILTER |
| 35647–38195 | 2549 | ACCOUNTS — SUPABASE CRUD |
| 38196–39010 | 815 | BULK ADD ACCOUNTS |
| 39011–39014 | 4 | END BULK ADD |
| 39015–39832 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 39833–39892 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 39893–40588 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 40589–40736 | 148 | LOT RECHNER |
| 40737–62939 | 22203 | TRADE PLANS |
| 62940–64263 | 1324 | FINANZEN |
| 64264–72149 | 7886 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 24044–25055 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 25056–30991 | P&L NACH DEM TRADE — DREI QUELLEN |
| 30992–31304 | SPANNE |
| 31305–36184 | WARTET |
| 36185–41889 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 41890–41947 | GEPLANTE TRADES FÜR POLAR |
| 41948 | ENDE GEPLANTE TRADES FÜR POLAR |
| 44021–46286 | ECHO V2 — Trade-Start ohne Hedge |
| 46287–47512 | REMOTE-TRADE-SIGNALE |
| 47513–48180 | AUTO-START-WARTESCHLANGE |
| 48181–48605 | V2 SCHLIESSEN |
| 48606 | ENDE V2 SCHLIESSEN |
| 49365 | ENDE REMOTE-TRADE-SIGNALE |
| 49367–49611 | BENACHRICHTIGUNGEN AUFS HANDY |
| 49612 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 49614–49823 | AUTO-CLOSE VOR MARKET CLOSE |
| 49824–50528 | GEPLANTE STARTZEIT |
| 50529–50832 | RICHTUNG AM START |
| 50833–51019 | START-FEHLER & NEU EINPLANEN |
| 51020 | ENDE START-FEHLER |
| 51444 | ENDE GEPLANTE STARTZEIT |
| 51446–52220 | AUTO-PLANER |
| 52221 | ENDE AUTO-PLANER |
| 52223–53968 | TRADE-PLANER-SEITE |
| 53969–55038 | HEUTE BEENDET |
| 55039 | ENDE TRADE-PLANER-SEITE |
| 55047 | ENDE AUTO-CLOSE |
| 58084–58122 | CHALLENGES MIT HEDGE |
| 58123–58667 | FUTURES VORPLANEN |
| 58668 | ENDE FUTURES VORPLANEN |
| 58670–60965 | WINNING-DAY-FARMER |
| 60966 | ENDE WINNING-DAY-FARMER |
| 60968–61086 | WD-ANBAU |
| 61087 | ENDE WD-ANBAU |
| 64313–64638 | MAIL-REITER |
| 64639 | ENDE MAIL-REITER |
| 64641–70072 | ADMIN → MAIL |
| 70073–70510 | ADMIN „TRADE-PLANER" |
| 70511–70622 | ID-DETAIL |
| 70623–70855 | GRUPPEN-PLANER |
| 70856 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 33430 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 33939 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 34426 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 34848 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 34953 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 64852 | SUPABASE-SYNC für localStorage-Daten |
| 65075 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 65558 | FX-Kurs USD/EUR |
| 65726 | JOURNAL — Tägliche Trading-Notizen |
| 66020 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 66384 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 66646 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (7280–13736)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 7808 | view: **overview** |
| 7921 | view: **accounts** |
| 8274 | modal: linkTopstepModal |
| 8315 | view: **topstep** |
| 8412 | view: **calc** |
| 8540 | view: **trades** |
| 8729 | modal: tpVorplanModal |
| 8822 | modal: tplBestModal |
| 8838 | modal: apKontoModal |
| 8849 | modal: handModal |
| 8858 | modal: apProbeModal |
| 8880 | modal: tpOrderModal |
| 8962 | modal: tradePlanModal |
| 9365 | modal: polarModal |
| 9459 | modal: polarCheckModal |
| 9493 | modal: tradeCompleteModal |
| 9616 | modal: successorModal |
| 9760 | modal: blownSummaryModal |
| 9797 | modal: tpPreflightModal |
| 9829 | modal: vcModal |
| 9865 | view: **risk** |
| 9883 | view: **advisor** |
| 9996 | modal: advisor-firm-modal |
| 10059 | modal: advisor-kb-modal |
| 10073 | modal: advisor-memory-modal |
| 10087 | modal: advisor-extract-modal |
| 10101 | view: **payouts** |
| 10350 | modal: finModal |
| 10446 | modal: finReceiveModal |
| 10477 | modal: finSettleModal |
| 10525 | view: **analytics** |
| 10543 | view: **journal** |
| 10631 | view: **account-detail** |
| 10680 | view: **livetrades** |
| 10713 | modal: linkDupModal |
| 10754 | modal: linkMt5Modal |
| 10795 | view: **managed** |
| 10886 | modal: mgSettleModal |
| 10933 | view: **notes** |
| 10953 | view: **mail** |
| 10984 | view: **news** |
| 11024 | view: **propbaum** |
| 11055 | view: **tplaner** |
| 11077 | view: **vorrat** |
| 11097 | view: **wdlive** |
| 11130 | view: **firmen** |
| 11176 | view: **markt** |
| 11246 | view: **mt5copier** |
| 11325 | view: **echoplus** |
| 11368 | modal: mtcAddModal |
| 11422 | view: **kasse** |
| 12837 | modal: walKommModal |
| 12883 | view: **settings** |
| 13025 | modal: customFirmModal |
| 13175 | modal: mwdErledigtModal |
| 13235 | modal: addAccountModal |
| 13554 | modal: credModal |
| 13571 | modal: bulkAddModal |

## app.py — Routen (29289 Zeilen)

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
| 3643 | `"/push/vapid-public", methods=["GET", "OPTIONS"]` |
| 3657 | `"/push/subscribe", methods=["POST", "OPTIONS"]` |
| 3689 | `"/push/unsubscribe", methods=["POST", "OPTIONS"]` |
| 3713 | `"/push/geraete", methods=["GET", "OPTIONS"]` |
| 3731 | `"/push/send", methods=["POST", "OPTIONS"]` |
| 3756 | `"/konto-weg/melden", methods=["POST", "OPTIONS"]` |
| 3801 | `"/sw.js", methods=["GET"]` |
| 6919 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7215 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7402 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7542 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7737 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 7834 | `"/admin/muster-portfolio", methods=["GET", "OPTIONS"]` |
| 9884 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 9913 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10292 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10312 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10373 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10389 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10519 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11361 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12340 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 12775 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 12827 | `"/pc-namen", methods=["GET", "OPTIONS"]` |
| 12975 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 13085 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 13736 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 13790 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 13824 | `"/health", methods=["GET", "OPTIONS"]` |
| 14170 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 14817 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 14904 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14963 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 15097 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 15140 | `"/code/stand", methods=["GET"]` |
| 15332 | `"/admin/puls-heim", methods=["GET", "OPTIONS"]` |
| 15352 | `"/richtung/frei", methods=["POST"]` |
| 15457 | `"/mail/eingang", methods=["POST"]` |
| 15623 | `"/admin/mail", methods=["GET", "PATCH", "OPTIONS"]` |
| 15686 | `"/admin/mail/<int:mid>", methods=["GET", "OPTIONS"]` |
| 15706 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 15760 | `"/code/tab-stand/<pc>", methods=["GET"]` |
| 15800 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 15883 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 15966 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 16095 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 16206 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16303 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 16373 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16392 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 18428 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 18561 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19294 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 25552 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 25603 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 25623 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 25768 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 26137 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 26376 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 26411 | `"/admin/auto-plan/waage-start", methods=["POST", "OPTIONS"]` |
| 26457 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 27558 | `"/admin/ziel-wache-jetzt", methods=["POST", "OPTIONS"]` |
| 28399 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 28404 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 28409 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 28414 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 28806 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 28814 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 28829 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 28856 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 28875 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |
| 28996 | `"/admin/kunden-zahlungen", methods=["GET", "OPTIONS"]` |
| 29004 | `"/admin/kunden-zahlungen/buchen", methods=["POST", "OPTIONS"]` |
| 29028 | `"/admin/kunden-zahlungen/aktiv", methods=["POST", "OPTIONS"]` |

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
| 4421 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 5384 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10677 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 10837 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 13817 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 13957 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 15111 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 16224 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 16318 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 17548 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 18254 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 19471 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 22350 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 28893 | WIEDERKEHRENDE BUCHUNGEN (14.10.2026, Finn: „unter Finanzen manuell einbuchen und recurring auswählen — jeden Monat am 2. zieht |
| 29084 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 29119 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (74300 Zeilen) und app.py._

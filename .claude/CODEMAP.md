# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (66818 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 25–6613 | 6589 |
| HTML-Markup (Views + Modals) | 6614–12736 | 6123 |
| **JS-Modul** (ein `<script type="module">`) | **12737–66522** | **53786** |
| Rest (CSS-/JS-Nachtrag) | 66523–66818 | 296 |

## prophos.html — JS-Sektionen (12737–66522)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 12772–12801 | 30 | VIEW SWITCHER |
| 12802–12839 | 38 | BOOT |
| 12840–13151 | 312 | USER HYDRATION |
| 13152–13171 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 13172–13197 | 26 | BANNERS |
| 13198–13220 | 23 | LOGIN |
| 13221–13253 | 33 | SIGNUP |
| 13254–13278 | 25 | RESET |
| 13279–13298 | 20 | LOGOUT |
| 13299–13314 | 16 | USER DROPDOWN |
| 13315–18432 | 5118 | DASHBOARD TABS |
| 18433–18486 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 18487–18784 | 298 | MOBILE SIDEBAR |
| 18785–18792 | 8 | DASHBOARD MOUNT |
| 18793–19061 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 19062–19355 | 294 | DUPLIKUM CONNECTION |
| 19356–19620 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 19621–20104 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 20105–20500 | 396 | DUPLIKUM LINKING (lokal) |
| 20501–22452 | 1952 | ENDE MT5-COPIER LINKING |
| 22453–23684 | 1232 | ENDE MT5-ROUTE |
| 23685–26491 | 2807 | ENDE ORBIT V2 |
| 26492–28800 | 2309 | ENDE FUSION-GEGENHEDGE |
| 28801–30375 | 1575 | ENDE MARKT LIVE |
| 30376–30506 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 30507–30956 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 30957–32896 | 1940 | DUPLIKUM AUTO-REFRESH |
| 32897–32983 | 87 | TRADE-COMPLETE: Status-Optionen |
| 32984–33347 | 364 | NACHFOLGER-WIZARD |
| 33348–33355 | 8 | ARCHIV-FILTER |
| 33356–35843 | 2488 | ACCOUNTS — SUPABASE CRUD |
| 35844–36596 | 753 | BULK ADD ACCOUNTS |
| 36597–36600 | 4 | END BULK ADD |
| 36601–37418 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 37419–37478 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 37479–38174 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 38175–38322 | 148 | LOT RECHNER |
| 38323–58120 | 19798 | TRADE PLANS |
| 58121–59374 | 1254 | FINANZEN |
| 59375–66522 | 7148 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 22570–23532 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 23533–29257 | P&L NACH DEM TRADE — DREI QUELLEN |
| 29258–29538 | SPANNE |
| 29539–33881 | WARTET |
| 33882–41320 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 41321–43513 | ECHO V2 — Trade-Start ohne Hedge |
| 43514–44655 | REMOTE-TRADE-SIGNALE |
| 44656–45323 | AUTO-START-WARTESCHLANGE |
| 45324–45748 | V2 SCHLIESSEN |
| 45749 | ENDE V2 SCHLIESSEN |
| 46465 | ENDE REMOTE-TRADE-SIGNALE |
| 46467–46711 | BENACHRICHTIGUNGEN AUFS HANDY |
| 46712 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 46714–46922 | AUTO-CLOSE VOR MARKET CLOSE |
| 46923–47598 | GEPLANTE STARTZEIT |
| 47599–47783 | RICHTUNG AM START |
| 47784–47948 | START-FEHLER & NEU EINPLANEN |
| 47949 | ENDE START-FEHLER |
| 48226 | ENDE GEPLANTE STARTZEIT |
| 48228–49002 | AUTO-PLANER |
| 49003 | ENDE AUTO-PLANER |
| 49005–50539 | TRADE-PLANER-SEITE |
| 50540–51547 | HEUTE BEENDET |
| 51548 | ENDE TRADE-PLANER-SEITE |
| 51556 | ENDE AUTO-CLOSE |
| 53514–53552 | CHALLENGES MIT HEDGE |
| 53553–54072 | FUTURES VORPLANEN |
| 54073 | ENDE FUTURES VORPLANEN |
| 54075–56334 | WINNING-DAY-FARMER |
| 56335 | ENDE WINNING-DAY-FARMER |
| 56337–56455 | WD-ANBAU |
| 56456 | ENDE WD-ANBAU |
| 64690–65076 | ADMIN „TRADE-PLANER" |
| 65077–65188 | ID-DETAIL |
| 65189–65419 | GRUPPEN-PLANER |
| 65420 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 31151 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 31660 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 32147 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 32569 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 32674 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 59487 | SUPABASE-SYNC für localStorage-Daten |
| 59710 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 60193 | FX-Kurs USD/EUR |
| 60361 | JOURNAL — Tägliche Trading-Notizen |
| 60655 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 61019 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 61281 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (6614–12736)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 7126 | view: **overview** |
| 7239 | view: **accounts** |
| 7572 | modal: linkTopstepModal |
| 7613 | view: **topstep** |
| 7710 | view: **calc** |
| 7838 | view: **trades** |
| 8025 | modal: tpVorplanModal |
| 8117 | modal: tplBestModal |
| 8133 | modal: apKontoModal |
| 8144 | modal: handModal |
| 8153 | modal: apProbeModal |
| 8175 | modal: tpOrderModal |
| 8257 | modal: tradePlanModal |
| 8660 | modal: polarModal |
| 8710 | modal: tradeCompleteModal |
| 8818 | modal: successorModal |
| 8962 | modal: blownSummaryModal |
| 8999 | modal: tpPreflightModal |
| 9031 | modal: vcModal |
| 9067 | view: **risk** |
| 9085 | view: **advisor** |
| 9198 | modal: advisor-firm-modal |
| 9261 | modal: advisor-kb-modal |
| 9275 | modal: advisor-memory-modal |
| 9289 | modal: advisor-extract-modal |
| 9303 | view: **payouts** |
| 9542 | modal: finModal |
| 9629 | modal: finReceiveModal |
| 9660 | modal: finSettleModal |
| 9708 | view: **analytics** |
| 9726 | view: **journal** |
| 9814 | view: **account-detail** |
| 9863 | view: **livetrades** |
| 9896 | modal: linkDupModal |
| 9937 | modal: linkMt5Modal |
| 9978 | view: **managed** |
| 10069 | modal: mgSettleModal |
| 10116 | view: **notes** |
| 10136 | view: **news** |
| 10176 | view: **propbaum** |
| 10207 | view: **tplaner** |
| 10229 | view: **vorrat** |
| 10249 | view: **wdlive** |
| 10280 | view: **firmen** |
| 10326 | view: **markt** |
| 10396 | view: **mt5copier** |
| 10475 | view: **echoplus** |
| 10518 | modal: mtcAddModal |
| 10572 | view: **kasse** |
| 11851 | modal: walKommModal |
| 11897 | view: **settings** |
| 12028 | modal: customFirmModal |
| 12178 | modal: mwdErledigtModal |
| 12238 | modal: addAccountModal |
| 12557 | modal: credModal |
| 12574 | modal: bulkAddModal |

## app.py — Routen (25791 Zeilen)

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
| 3798 | `"/sw.js", methods=["GET"]` |
| 6739 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7035 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7222 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7362 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7557 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 9624 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 9653 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10032 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10052 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10113 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10129 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10259 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11093 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12023 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 12403 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 12531 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 12641 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 13273 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 13327 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 13361 | `"/health", methods=["GET", "OPTIONS"]` |
| 13707 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 14352 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 14439 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14498 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 14632 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 14675 | `"/code/stand", methods=["GET"]` |
| 14693 | `"/richtung/frei", methods=["POST"]` |
| 14729 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 14754 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 14837 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 14920 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 15049 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 15160 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15257 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 15327 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15346 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 17001 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 17134 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 17865 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 23099 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 23141 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 23161 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 23306 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 23675 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 23824 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 23859 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 25074 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 25079 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 25084 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 25089 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 25469 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 25477 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 25492 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 25519 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 25538 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |

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
| 4418 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 5381 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10417 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 10577 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 13354 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 13494 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 14646 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 15178 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 15272 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 16160 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 16827 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 18042 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 20449 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 25592 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 25627 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (66818 Zeilen) und app.py._

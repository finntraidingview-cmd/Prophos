# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (75228 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 49–7366 | 7318 |
| HTML-Markup (Views + Modals) | 7367–13850 | 6484 |
| **JS-Modul** (ein `<script type="module">`) | **13851–73077** | **59227** |
| Rest (CSS-/JS-Nachtrag) | 73078–75228 | 2151 |

## prophos.html — JS-Sektionen (13851–73077)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 13886–13915 | 30 | VIEW SWITCHER |
| 13916–13953 | 38 | BOOT |
| 13954–14296 | 343 | USER HYDRATION |
| 14297–14316 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 14317–14342 | 26 | BANNERS |
| 14343–14365 | 23 | LOGIN |
| 14366–14398 | 33 | SIGNUP |
| 14399–14423 | 25 | RESET |
| 14424–14443 | 20 | LOGOUT |
| 14444–14459 | 16 | USER DROPDOWN |
| 14460–19907 | 5448 | DASHBOARD TABS |
| 19908–19961 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 19962–20271 | 310 | MOBILE SIDEBAR |
| 20272–20279 | 8 | DASHBOARD MOUNT |
| 20280–20548 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 20549–20842 | 294 | DUPLIKUM CONNECTION |
| 20843–21107 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 21108–21591 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 21592–21987 | 396 | DUPLIKUM LINKING (lokal) |
| 21988–24042 | 2055 | ENDE MT5-COPIER LINKING |
| 24043–25506 | 1464 | ENDE MT5-ROUTE |
| 25507–28529 | 3023 | ENDE ORBIT V2 |
| 28530–30927 | 2398 | ENDE FUSION-GEGENHEDGE |
| 30928–33179 | 2252 | ENDE MARKT LIVE |
| 33180–33310 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 33311–33760 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 33761–35705 | 1945 | DUPLIKUM AUTO-REFRESH |
| 35706–35795 | 90 | TRADE-COMPLETE: Status-Optionen |
| 35796–36205 | 410 | NACHFOLGER-WIZARD |
| 36206–36213 | 8 | ARCHIV-FILTER |
| 36214–38765 | 2552 | ACCOUNTS — SUPABASE CRUD |
| 38766–39580 | 815 | BULK ADD ACCOUNTS |
| 39581–39584 | 4 | END BULK ADD |
| 39585–40402 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 40403–40462 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 40463–41158 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 41159–41306 | 148 | LOT RECHNER |
| 41307–63829 | 22523 | TRADE PLANS |
| 63830–65153 | 1324 | FINANZEN |
| 65154–73077 | 7924 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 24187–25354 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 25355–31462 | P&L NACH DEM TRADE — DREI QUELLEN |
| 31463–31775 | SPANNE |
| 31776–36751 | WARTET |
| 36752–42459 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 42460–42517 | GEPLANTE TRADES FÜR POLAR |
| 42518 | ENDE GEPLANTE TRADES FÜR POLAR |
| 44593–46878 | ECHO V2 — Trade-Start ohne Hedge |
| 46879–48120 | REMOTE-TRADE-SIGNALE |
| 48121–48788 | AUTO-START-WARTESCHLANGE |
| 48789–49213 | V2 SCHLIESSEN |
| 49214 | ENDE V2 SCHLIESSEN |
| 49973 | ENDE REMOTE-TRADE-SIGNALE |
| 49975–50247 | BENACHRICHTIGUNGEN AUFS HANDY |
| 50248 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 50250–50459 | AUTO-CLOSE VOR MARKET CLOSE |
| 50460–51174 | GEPLANTE STARTZEIT |
| 51175–51517 | RICHTUNG AM START |
| 51518–51741 | START-FEHLER & NEU EINPLANEN |
| 51742 | ENDE START-FEHLER |
| 52166 | ENDE GEPLANTE STARTZEIT |
| 52168–52942 | AUTO-PLANER |
| 52943 | ENDE AUTO-PLANER |
| 52945–54707 | TRADE-PLANER-SEITE |
| 54708–55777 | HEUTE BEENDET |
| 55778 | ENDE TRADE-PLANER-SEITE |
| 55786 | ENDE AUTO-CLOSE |
| 58825–58863 | CHALLENGES MIT HEDGE |
| 58864–59425 | FUTURES VORPLANEN |
| 59426 | ENDE FUTURES VORPLANEN |
| 59428–61758 | WINNING-DAY-FARMER |
| 61759 | ENDE WINNING-DAY-FARMER |
| 61761–61879 | WD-ANBAU |
| 61880 | ENDE WD-ANBAU |
| 65203–65528 | MAIL-REITER |
| 65529 | ENDE MAIL-REITER |
| 65531–70984 | ADMIN → MAIL |
| 70985–71422 | ADMIN „TRADE-PLANER" |
| 71423–71534 | ID-DETAIL |
| 71535–71767 | GRUPPEN-PLANER |
| 71768 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 33955 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 34464 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 34951 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 35373 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 35478 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 65742 | SUPABASE-SYNC für localStorage-Daten |
| 65965 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 66448 | FX-Kurs USD/EUR |
| 66616 | JOURNAL — Tägliche Trading-Notizen |
| 66910 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 67274 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 67536 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (7367–13850)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 7895 | view: **overview** |
| 8008 | view: **accounts** |
| 8363 | modal: linkTopstepModal |
| 8404 | view: **topstep** |
| 8501 | view: **calc** |
| 8629 | view: **trades** |
| 8818 | modal: tpVorplanModal |
| 8912 | modal: tplBestModal |
| 8928 | modal: apKontoModal |
| 8939 | modal: handModal |
| 8948 | modal: apProbeModal |
| 8970 | modal: tpOrderModal |
| 9052 | modal: tradePlanModal |
| 9455 | modal: polarModal |
| 9549 | modal: polarCheckModal |
| 9583 | modal: tradeCompleteModal |
| 9708 | modal: successorModal |
| 9852 | modal: blownSummaryModal |
| 9889 | modal: tpPreflightModal |
| 9921 | modal: vcModal |
| 9957 | view: **risk** |
| 9975 | view: **advisor** |
| 10088 | modal: advisor-firm-modal |
| 10151 | modal: advisor-kb-modal |
| 10165 | modal: advisor-memory-modal |
| 10179 | modal: advisor-extract-modal |
| 10193 | view: **payouts** |
| 10442 | modal: finModal |
| 10538 | modal: finReceiveModal |
| 10569 | modal: finSettleModal |
| 10617 | view: **analytics** |
| 10635 | view: **journal** |
| 10723 | view: **account-detail** |
| 10772 | view: **livetrades** |
| 10805 | modal: linkDupModal |
| 10846 | modal: linkMt5Modal |
| 10887 | view: **managed** |
| 10978 | modal: mgSettleModal |
| 11025 | view: **notes** |
| 11045 | view: **mail** |
| 11076 | view: **news** |
| 11116 | view: **propbaum** |
| 11147 | view: **tplaner** |
| 11169 | view: **vorrat** |
| 11189 | view: **wdlive** |
| 11222 | view: **firmen** |
| 11268 | view: **markt** |
| 11338 | view: **mt5copier** |
| 11417 | view: **echoplus** |
| 11460 | modal: mtcAddModal |
| 11514 | view: **kasse** |
| 12934 | modal: walKommModal |
| 12980 | view: **settings** |
| 13139 | modal: customFirmModal |
| 13289 | modal: mwdErledigtModal |
| 13349 | modal: addAccountModal |
| 13668 | modal: credModal |
| 13685 | modal: bulkAddModal |

## app.py — Routen (29772 Zeilen)

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
| 7177 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7473 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7660 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7800 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7995 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 8092 | `"/admin/muster-portfolio", methods=["GET", "OPTIONS"]` |
| 10142 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 10171 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10550 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10570 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10631 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10647 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10777 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11624 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12603 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 13038 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 13090 | `"/pc-namen", methods=["GET", "OPTIONS"]` |
| 13238 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 13348 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 13999 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 14053 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 14087 | `"/health", methods=["GET", "OPTIONS"]` |
| 14433 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 15080 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 15167 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15226 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 15360 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 15403 | `"/code/stand", methods=["GET"]` |
| 15651 | `"/admin/puls-heim", methods=["GET", "OPTIONS"]` |
| 15671 | `"/richtung/frei", methods=["POST"]` |
| 15776 | `"/mail/eingang", methods=["POST"]` |
| 15942 | `"/admin/mail", methods=["GET", "PATCH", "OPTIONS"]` |
| 16005 | `"/admin/mail/<int:mid>", methods=["GET", "OPTIONS"]` |
| 16025 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 16079 | `"/code/tab-stand/<pc>", methods=["GET"]` |
| 16119 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 16202 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 16285 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 16414 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 16525 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16622 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 16692 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16711 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 18753 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 18886 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19619 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 25924 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 25975 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 25995 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 26140 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 26509 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 26748 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 26783 | `"/admin/auto-plan/waage-start", methods=["POST", "OPTIONS"]` |
| 26829 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 27971 | `"/admin/ziel-wache-jetzt", methods=["POST", "OPTIONS"]` |
| 28882 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 28887 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 28892 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 28897 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 29289 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 29297 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 29312 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 29339 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 29358 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |
| 29479 | `"/admin/kunden-zahlungen", methods=["GET", "OPTIONS"]` |
| 29487 | `"/admin/kunden-zahlungen/buchen", methods=["POST", "OPTIONS"]` |
| 29511 | `"/admin/kunden-zahlungen/aktiv", methods=["POST", "OPTIONS"]` |

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
| 5641 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10935 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 11095 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 14080 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 14220 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 15374 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 16543 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 16637 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 17873 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 18579 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 19796 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 22722 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 29376 | WIEDERKEHRENDE BUCHUNGEN (14.10.2026, Finn: „unter Finanzen manuell einbuchen und recurring auswählen — jeden Monat am 2. zieht |
| 29567 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 29602 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (75228 Zeilen) und app.py._

# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (74985 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 49–7321 | 7273 |
| HTML-Markup (Views + Modals) | 7322–13802 | 6481 |
| **JS-Modul** (ein `<script type="module">`) | **13803–72834** | **59032** |
| Rest (CSS-/JS-Nachtrag) | 72835–74985 | 2151 |

## prophos.html — JS-Sektionen (13803–72834)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 13838–13867 | 30 | VIEW SWITCHER |
| 13868–13905 | 38 | BOOT |
| 13906–14248 | 343 | USER HYDRATION |
| 14249–14268 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 14269–14294 | 26 | BANNERS |
| 14295–14317 | 23 | LOGIN |
| 14318–14350 | 33 | SIGNUP |
| 14351–14375 | 25 | RESET |
| 14376–14395 | 20 | LOGOUT |
| 14396–14411 | 16 | USER DROPDOWN |
| 14412–19859 | 5448 | DASHBOARD TABS |
| 19860–19913 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 19914–20223 | 310 | MOBILE SIDEBAR |
| 20224–20231 | 8 | DASHBOARD MOUNT |
| 20232–20500 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 20501–20794 | 294 | DUPLIKUM CONNECTION |
| 20795–21059 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 21060–21543 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 21544–21939 | 396 | DUPLIKUM LINKING (lokal) |
| 21940–23994 | 2055 | ENDE MT5-COPIER LINKING |
| 23995–25458 | 1464 | ENDE MT5-ROUTE |
| 25459–28450 | 2992 | ENDE ORBIT V2 |
| 28451–30809 | 2359 | ENDE FUSION-GEGENHEDGE |
| 30810–33057 | 2248 | ENDE MARKT LIVE |
| 33058–33188 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 33189–33638 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 33639–35583 | 1945 | DUPLIKUM AUTO-REFRESH |
| 35584–35673 | 90 | TRADE-COMPLETE: Status-Optionen |
| 35674–36083 | 410 | NACHFOLGER-WIZARD |
| 36084–36091 | 8 | ARCHIV-FILTER |
| 36092–38643 | 2552 | ACCOUNTS — SUPABASE CRUD |
| 38644–39458 | 815 | BULK ADD ACCOUNTS |
| 39459–39462 | 4 | END BULK ADD |
| 39463–40280 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 40281–40340 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 40341–41036 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 41037–41184 | 148 | LOT RECHNER |
| 41185–63586 | 22402 | TRADE PLANS |
| 63587–64910 | 1324 | FINANZEN |
| 64911–72834 | 7924 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 24139–25306 | RÜCK-LOGIN INS BIG-TRADE-KONTO |
| 25307–31340 | P&L NACH DEM TRADE — DREI QUELLEN |
| 31341–31653 | SPANNE |
| 31654–36629 | WARTET |
| 36630–42337 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 42338–42395 | GEPLANTE TRADES FÜR POLAR |
| 42396 | ENDE GEPLANTE TRADES FÜR POLAR |
| 44471–46756 | ECHO V2 — Trade-Start ohne Hedge |
| 46757–47997 | REMOTE-TRADE-SIGNALE |
| 47998–48665 | AUTO-START-WARTESCHLANGE |
| 48666–49090 | V2 SCHLIESSEN |
| 49091 | ENDE V2 SCHLIESSEN |
| 49850 | ENDE REMOTE-TRADE-SIGNALE |
| 49852–50124 | BENACHRICHTIGUNGEN AUFS HANDY |
| 50125 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 50127–50336 | AUTO-CLOSE VOR MARKET CLOSE |
| 50337–51049 | GEPLANTE STARTZEIT |
| 51050–51392 | RICHTUNG AM START |
| 51393–51610 | START-FEHLER & NEU EINPLANEN |
| 51611 | ENDE START-FEHLER |
| 52035 | ENDE GEPLANTE STARTZEIT |
| 52037–52811 | AUTO-PLANER |
| 52812 | ENDE AUTO-PLANER |
| 52814–54574 | TRADE-PLANER-SEITE |
| 54575–55644 | HEUTE BEENDET |
| 55645 | ENDE TRADE-PLANER-SEITE |
| 55653 | ENDE AUTO-CLOSE |
| 58692–58730 | CHALLENGES MIT HEDGE |
| 58731–59279 | FUTURES VORPLANEN |
| 59280 | ENDE FUTURES VORPLANEN |
| 59282–61612 | WINNING-DAY-FARMER |
| 61613 | ENDE WINNING-DAY-FARMER |
| 61615–61733 | WD-ANBAU |
| 61734 | ENDE WD-ANBAU |
| 64960–65285 | MAIL-REITER |
| 65286 | ENDE MAIL-REITER |
| 65288–70741 | ADMIN → MAIL |
| 70742–71179 | ADMIN „TRADE-PLANER" |
| 71180–71291 | ID-DETAIL |
| 71292–71524 | GRUPPEN-PLANER |
| 71525 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 33833 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 34342 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 34829 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 35251 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 35356 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 65499 | SUPABASE-SYNC für localStorage-Daten |
| 65722 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 66205 | FX-Kurs USD/EUR |
| 66373 | JOURNAL — Tägliche Trading-Notizen |
| 66667 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 67031 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 67293 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (7322–13802)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 7850 | view: **overview** |
| 7963 | view: **accounts** |
| 8318 | modal: linkTopstepModal |
| 8359 | view: **topstep** |
| 8456 | view: **calc** |
| 8584 | view: **trades** |
| 8773 | modal: tpVorplanModal |
| 8866 | modal: tplBestModal |
| 8882 | modal: apKontoModal |
| 8893 | modal: handModal |
| 8902 | modal: apProbeModal |
| 8924 | modal: tpOrderModal |
| 9006 | modal: tradePlanModal |
| 9409 | modal: polarModal |
| 9503 | modal: polarCheckModal |
| 9537 | modal: tradeCompleteModal |
| 9660 | modal: successorModal |
| 9804 | modal: blownSummaryModal |
| 9841 | modal: tpPreflightModal |
| 9873 | modal: vcModal |
| 9909 | view: **risk** |
| 9927 | view: **advisor** |
| 10040 | modal: advisor-firm-modal |
| 10103 | modal: advisor-kb-modal |
| 10117 | modal: advisor-memory-modal |
| 10131 | modal: advisor-extract-modal |
| 10145 | view: **payouts** |
| 10394 | modal: finModal |
| 10490 | modal: finReceiveModal |
| 10521 | modal: finSettleModal |
| 10569 | view: **analytics** |
| 10587 | view: **journal** |
| 10675 | view: **account-detail** |
| 10724 | view: **livetrades** |
| 10757 | modal: linkDupModal |
| 10798 | modal: linkMt5Modal |
| 10839 | view: **managed** |
| 10930 | modal: mgSettleModal |
| 10977 | view: **notes** |
| 10997 | view: **mail** |
| 11028 | view: **news** |
| 11068 | view: **propbaum** |
| 11099 | view: **tplaner** |
| 11121 | view: **vorrat** |
| 11141 | view: **wdlive** |
| 11174 | view: **firmen** |
| 11220 | view: **markt** |
| 11290 | view: **mt5copier** |
| 11369 | view: **echoplus** |
| 11412 | modal: mtcAddModal |
| 11466 | view: **kasse** |
| 12886 | modal: walKommModal |
| 12932 | view: **settings** |
| 13091 | modal: customFirmModal |
| 13241 | modal: mwdErledigtModal |
| 13301 | modal: addAccountModal |
| 13620 | modal: credModal |
| 13637 | modal: bulkAddModal |

## app.py — Routen (29771 Zeilen)

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
| 7176 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 7472 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7659 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7799 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7994 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 8091 | `"/admin/muster-portfolio", methods=["GET", "OPTIONS"]` |
| 10141 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 10170 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 10549 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 10569 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 10630 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 10646 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10776 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 11623 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 12602 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 13037 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 13089 | `"/pc-namen", methods=["GET", "OPTIONS"]` |
| 13237 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 13347 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 13998 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 14052 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 14086 | `"/health", methods=["GET", "OPTIONS"]` |
| 14432 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 15079 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 15166 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15225 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 15359 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 15402 | `"/code/stand", methods=["GET"]` |
| 15650 | `"/admin/puls-heim", methods=["GET", "OPTIONS"]` |
| 15670 | `"/richtung/frei", methods=["POST"]` |
| 15775 | `"/mail/eingang", methods=["POST"]` |
| 15941 | `"/admin/mail", methods=["GET", "PATCH", "OPTIONS"]` |
| 16004 | `"/admin/mail/<int:mid>", methods=["GET", "OPTIONS"]` |
| 16024 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 16078 | `"/code/tab-stand/<pc>", methods=["GET"]` |
| 16118 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 16201 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 16284 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 16413 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 16524 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16621 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 16691 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16710 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 18752 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 18885 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 19618 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 25923 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 25974 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 25994 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 26139 | `"/admin/gruppen-plan", methods=["GET", "POST", "OPTIONS"]` |
| 26508 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 26747 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 26782 | `"/admin/auto-plan/waage-start", methods=["POST", "OPTIONS"]` |
| 26828 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 27970 | `"/admin/ziel-wache-jetzt", methods=["POST", "OPTIONS"]` |
| 28881 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 28886 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 28891 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 28896 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 29288 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 29296 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 29311 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 29338 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 29357 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |
| 29478 | `"/admin/kunden-zahlungen", methods=["GET", "OPTIONS"]` |
| 29486 | `"/admin/kunden-zahlungen/buchen", methods=["POST", "OPTIONS"]` |
| 29510 | `"/admin/kunden-zahlungen/aktiv", methods=["POST", "OPTIONS"]` |

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
| 10934 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 11094 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 14079 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 14219 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 15373 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 16542 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 16636 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 17872 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 18578 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 19795 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 22721 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 29375 | WIEDERKEHRENDE BUCHUNGEN (14.10.2026, Finn: „unter Finanzen manuell einbuchen und recurring auswählen — jeden Monat am 2. zieht |
| 29566 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 29601 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (74985 Zeilen) und app.py._

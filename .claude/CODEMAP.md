# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (61229 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 25–6129 | 6105 |
| HTML-Markup (Views + Modals) | 6130–12116 | 5987 |
| **JS-Modul** (ein `<script type="module">`) | **12117–60933** | **48817** |
| Rest (CSS-/JS-Nachtrag) | 60934–61229 | 296 |

## prophos.html — JS-Sektionen (12117–60933)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 12152–12181 | 30 | VIEW SWITCHER |
| 12182–12219 | 38 | BOOT |
| 12220–12516 | 297 | USER HYDRATION |
| 12517–12536 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 12537–12562 | 26 | BANNERS |
| 12563–12585 | 23 | LOGIN |
| 12586–12618 | 33 | SIGNUP |
| 12619–12643 | 25 | RESET |
| 12644–12663 | 20 | LOGOUT |
| 12664–12679 | 16 | USER DROPDOWN |
| 12680–17689 | 5010 | DASHBOARD TABS |
| 17690–17743 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 17744–18021 | 278 | MOBILE SIDEBAR |
| 18022–18029 | 8 | DASHBOARD MOUNT |
| 18030–18298 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 18299–18592 | 294 | DUPLIKUM CONNECTION |
| 18593–18857 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 18858–19341 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 19342–19737 | 396 | DUPLIKUM LINKING (lokal) |
| 19738–21673 | 1936 | ENDE MT5-COPIER LINKING |
| 21674–22656 | 983 | ENDE MT5-ROUTE |
| 22657–25074 | 2418 | ENDE ORBIT V2 |
| 25075–27274 | 2200 | ENDE FUSION-GEGENHEDGE |
| 27275–28295 | 1021 | ENDE MARKT LIVE |
| 28296–28426 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 28427–28876 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 28877–30768 | 1892 | DUPLIKUM AUTO-REFRESH |
| 30769–30855 | 87 | TRADE-COMPLETE: Status-Optionen |
| 30856–31170 | 315 | NACHFOLGER-WIZARD |
| 31171–31178 | 8 | ARCHIV-FILTER |
| 31179–33524 | 2346 | ACCOUNTS — SUPABASE CRUD |
| 33525–34277 | 753 | BULK ADD ACCOUNTS |
| 34278–34281 | 4 | END BULK ADD |
| 34282–35099 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 35100–35159 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 35160–35855 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 35856–36003 | 148 | LOT RECHNER |
| 36004–53186 | 17183 | TRADE PLANS |
| 53187–54430 | 1244 | FINANZEN |
| 54431–60933 | 6503 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 12290–20164 | SPEICHER VOLL |
| 20165–20174 | V2-WEGE |
| 20175–20299 | PULS FÜR TOPSTEP |
| 20300–20617 | PC-KENNUNG VOM PANEL |
| 20618–21473 | FIRMEN-SCHLÜSSEL FÜR DEN RICHTUNGSSCHUTZ |
| 21474–21838 | ECHO V2 |
| 21839–21904 | MT5-BALANCE DAUERHAFT AM KONTO |
| 21905–21960 | MT5-BALANCE JETZT LESEN |
| 21961–21966 | BALANCE JETZT LESEN |
| 21967–22085 | WARTESCHLANGE FÜR BALANCE-LESUNGEN |
| 22086–22130 | TOPSTEP V2 START-BASELINE AUS DER ORDER-ANTWORT |
| 22131–22505 | ORBIT V2 START-BASELINE AUS DER ORDER-ANTWORT |
| 22506–22720 | P&L NACH DEM TRADE — DREI QUELLEN |
| 22721–22879 | P/L-EINGABE |
| 22880–23163 | LIQUIDATIONS-LEVEL STATT MASTER-SL |
| 23164–23290 | PUFFER OHNE ECHTEN FILL |
| 23291–23325 | EINSTIEG AUS DEM PULS-FILL NACHTRAGEN |
| 23326–23391 | FRÜHER FUSION-HEDGE |
| 23392–23407 | PULS-ENDLESUNG |
| 23408–23444 | LOGIN-BREMSE |
| 23445–23592 | KONTO WEG |
| 23593–23646 | FOLGETRADE |
| 23647–23940 | KONTO-BEFUND PERSISTIEREN |
| 23941–23946 | DEMO-ENDE |
| 23947–24076 | HANDSTART-EINSTIEG |
| 24077–24267 | AUSSCHLAG-SCHUTZ |
| 24268–24307 | FEED-PUFFER FÜR DEN KLICKZEITPUNKT |
| 24308–24454 | TERMINAL-LEVEL AM ECHTEN TRADINGVIEW-FILL |
| 24455–24525 | READER-STAND FÜR DEN HEDGE-WÄCHTER |
| 24526–24583 | SCHNELL-WÄCHTER |
| 24584–24641 | MASTER LAUT READER |
| 24642–24912 | END-BALANCE AUS DEM USERSCRIPT |
| 24913–25579 | MASTER-WEG-SCHUTZ SICHTBAR |
| 25580–25607 | EINSTIEGS-MARKER JE LAUFENDEM WINNING DAY |
| 25608–25756 | POSITIONS-ZONEN WIE IN TRADINGVIEW |
| 25757–25842 | BETRETEN |
| 25843–25858 | KANÄLE NUR, WO SIE GEBRAUCHT WERDEN |
| 25859–25976 | PC-TAB BRAUCHT DEN LIVE-KURS |
| 25977–26037 | FEED-DIAGNOSE |
| 26038–26176 | PLAN HEUTE NACHT |
| 26177–26255 | INLINE-BEARBEITUNG |
| 26256–26277 | PLAN NEU ANLEGEN |
| 26278–26300 | BALANCE JE KONTO |
| 26301–26595 | ZEITSTRAHL |
| 26596–26602 | ZUM ABHAKEN |
| 26603–27017 | ENDLESUNG SICHTBAR |
| 27018–27020 | ECHTER TP AUS TV |
| 27021–27294 | ECHTER ENTRY AUS TV |
| 27295–27403 | ECHO IM RADAR |
| 27404–27541 | PC-TAB-LEBENSZEICHEN JE ID |
| 27542–27579 | LIVE-P&L DES MASTER-KONTOS |
| 27580–27658 | SPANNE |
| 27659–27675 | WARTET |
| 27676–27716 | LESUNG VERLOREN |
| 27717–27745 | BLOW ERKENNEN |
| 27746–27769 | APEX-EVAL-SOFTBREACH |
| 27770–27797 | BESTANDEN-FLAG |
| 27798–27827 | ANSEHEN |
| 27828–29648 | MANUELLE ARBEIT |
| 29649–31701 | SUPABASE-DIÄT |
| 31702–31836 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 31837–32099 | AUTO-PLANER-CHIP |
| 32100–33386 | KONTOWERT-SPALTE |
| 33387–38594 | ECHO NACH DER BULK-ANLAGE |
| 38595–40679 | ECHO V2 — Trade-Start ohne Hedge |
| 40680–40946 | REMOTE-TRADE-SIGNALE |
| 40947–41645 | KONTO WEG BEIM START |
| 41646–41664 | ECHO-V2-CHECKS NACHEINANDER |
| 41665–42297 | AUTO-START-WARTESCHLANGE |
| 42298–42456 | V2 SCHLIESSEN |
| 42457–42711 | PULS-ERGEBNISSE ÜBERNEHMEN |
| 42712 | ENDE V2 SCHLIESSEN |
| 42824–43305 | CLAIMS DIESES TABS MERKEN |
| 43306–43315 | LEERLAUF-TAKT DES EMPFÄNGERS |
| 43316–43404 | SUPABASE-DIÄT |
| 43405 | ENDE REMOTE-TRADE-SIGNALE |
| 43407–43651 | BENACHRICHTIGUNGEN AUFS HANDY |
| 43652 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 43654–43858 | AUTO-CLOSE VOR MARKET CLOSE |
| 43859–44033 | GEPLANTE STARTZEIT |
| 44034–44041 | NÄCHSTER PULS-EINSATZ |
| 44042–44222 | PULS LÄUFT GERADE |
| 44223–44317 | COUNTDOWN |
| 44318–44325 | SLAVE-VORPRÜFUNG VOR DEM WD-START |
| 44326–44383 | FUSION-MARGE |
| 44384–44521 | VORPRÜFLISTE |
| 44522–44618 | RICHTUNG AM START |
| 44619–44729 | START-FEHLER & NEU EINPLANEN |
| 44730–44742 | PULS-SPUR AM PLAN |
| 44743 | ENDE START-FEHLER |
| 44745–44973 | STARTZEIT-WARTESCHLANGE |
| 44974 | ENDE GEPLANTE STARTZEIT |
| 44976–45716 | AUTO-PLANER |
| 45717 | ENDE AUTO-PLANER |
| 45719–45913 | TRADE-PLANER-SEITE |
| 45914–45923 | ZEITSTRAHL V2 |
| 45924–46029 | PILLEN STATT KÜRZEL |
| 46030–46199 | NETTO-CHART |
| 46200–46229 | BRAUCHT DICH |
| 46230–46379 | WAS TUN |
| 46380–46451 | RECHTE FÜR FREMDE VORSCHLÄGE |
| 46452–46531 | HYPO-P&L |
| 46532–46583 | HYPO-P&L-CHART |
| 46584–46773 | BEENDET · BILANZ DES RECHNERS |
| 46774–46788 | HYPO-BILANZ |
| 46789–46802 | KERZEN FÜR DEN HYPO-P&L-VERLAUF |
| 46803–47062 | BOOT-CACHE DER PLANER-SEITE |
| 47063 | ENDE TRADE-PLANER-SEITE |
| 47071 | ENDE AUTO-CLOSE |
| 47865–48881 | WINNING-DAY-FUSION-HEDGE IN DEN GESAMTKOSTEN |
| 48882–49038 | FUTURES VORPLANEN |
| 49039–49066 | TOPSTEP EXPRESS |
| 49067–49390 | KONTOGRÖSSE FÜR DIE ANZEIGE |
| 49391 | ENDE FUTURES VORPLANEN |
| 49393–49484 | WINNING-DAY-FARMER |
| 49485–49552 | RICHTUNG ÜBERNEHMEN |
| 49553–50569 | BLÖCKE PER DRAG & DROP |
| 50570–50683 | ID OHNE NEU-WÜRFELN EINPLANEN |
| 50684–51436 | RICHTUNG PER KLICK |
| 51437 | ENDE WINNING-DAY-FARMER |
| 51439–51555 | WD-ANBAU |
| 51556 | ENDE WD-ANBAU |
| 53973–58771 | KONTO-AUSWAHL NACH PROP-FIRMA |
| 58772–58812 | BRÜCKEN-SCHUTZ |
| 58813–58833 | READER-DIREKTFEED |
| 58834–59633 | CODE-SCHLÜSSEL FÜRS PANEL |
| 59634–59704 | ADMIN „TRADE-PLANER" |
| 59705–59839 | ZU BESTÄTIGEN IM FIRMEN-BLOCK-DESIGN |
| 59840 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 29071 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 29608 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 30095 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 30517 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 30622 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 54543 | SUPABASE-SYNC für localStorage-Daten |
| 54766 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 55249 | FX-Kurs USD/EUR |
| 55417 | JOURNAL — Tägliche Trading-Notizen |
| 55711 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 56075 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 56337 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (6130–12116)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 6636 | view: **overview** |
| 6749 | view: **accounts** |
| 7081 | modal: linkTopstepModal |
| 7122 | view: **topstep** |
| 7219 | view: **calc** |
| 7347 | view: **trades** |
| 7516 | modal: tpVorplanModal |
| 7608 | modal: tplBestModal |
| 7624 | modal: apKontoModal |
| 7633 | modal: apProbeModal |
| 7655 | modal: tpOrderModal |
| 7737 | modal: tradePlanModal |
| 8125 | modal: tradeCompleteModal |
| 8233 | modal: successorModal |
| 8377 | modal: blownSummaryModal |
| 8414 | modal: tpPreflightModal |
| 8446 | modal: vcModal |
| 8482 | view: **risk** |
| 8500 | view: **advisor** |
| 8613 | modal: advisor-firm-modal |
| 8676 | modal: advisor-kb-modal |
| 8690 | modal: advisor-memory-modal |
| 8704 | modal: advisor-extract-modal |
| 8718 | view: **payouts** |
| 8957 | modal: finModal |
| 9044 | modal: finReceiveModal |
| 9075 | modal: finSettleModal |
| 9123 | view: **analytics** |
| 9141 | view: **journal** |
| 9229 | view: **account-detail** |
| 9278 | view: **livetrades** |
| 9311 | modal: linkDupModal |
| 9352 | modal: linkMt5Modal |
| 9393 | view: **managed** |
| 9484 | modal: mgSettleModal |
| 9531 | view: **notes** |
| 9551 | view: **news** |
| 9591 | view: **propbaum** |
| 9622 | view: **tplaner** |
| 9644 | view: **vorrat** |
| 9664 | view: **wdlive** |
| 9695 | view: **firmen** |
| 9741 | view: **markt** |
| 9811 | view: **mt5copier** |
| 9890 | view: **echoplus** |
| 9933 | modal: mtcAddModal |
| 9987 | view: **kasse** |
| 11244 | modal: walKommModal |
| 11290 | view: **settings** |
| 11421 | modal: customFirmModal |
| 11571 | modal: mwdErledigtModal |
| 11631 | modal: addAccountModal |
| 11938 | modal: credModal |
| 11955 | modal: bulkAddModal |

## app.py — Routen (17883 Zeilen)

| Zeile | Route |
|---|---|
| 47 | `"/version", methods=["GET"]` |
| 71 | `"/news/calendar", methods=["GET", "OPTIONS"]` |
| 172 | `"/markt/futures", methods=["GET", "OPTIONS"]` |
| 349 | `"/"` |
| 393 | `"/mt5-copier/VERSION", methods=["GET"]` |
| 435 | `"/api/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 449 | `"/ma/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 477 | `"/copier/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 561 | `"/local/restart-stack", methods=["POST", "OPTIONS"]` |
| 627 | `"/duplikum/connect", methods=["POST","OPTIONS"]` |
| 732 | `"/duplikum/session", methods=["GET", "OPTIONS"]` |
| 772 | `"/duplikum/<path:path>", methods=["GET","POST","OPTIONS"]` |
| 929 | `"/duplikum/refresh", methods=["POST","OPTIONS"]` |
| 967 | `"/duplikum/disconnect", methods=["POST","OPTIONS"]` |
| 1183 | `"/mirror/start", methods=["POST","OPTIONS"]` |
| 1191 | `"/mirror/stop", methods=["POST","OPTIONS"]` |
| 1206 | `"/mirror/status", methods=["GET"]` |
| 1305 | `"/mirror/diagnose", methods=["POST", "OPTIONS", "GET"]` |
| 2629 | `"/debug/account", methods=["POST","OPTIONS"]` |
| 3337 | `"/push/vapid-public", methods=["GET", "OPTIONS"]` |
| 3351 | `"/push/subscribe", methods=["POST", "OPTIONS"]` |
| 3383 | `"/push/unsubscribe", methods=["POST", "OPTIONS"]` |
| 3407 | `"/push/geraete", methods=["GET", "OPTIONS"]` |
| 3425 | `"/push/send", methods=["POST", "OPTIONS"]` |
| 3442 | `"/sw.js", methods=["GET"]` |
| 6303 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 6599 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 6786 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 6924 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7119 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 9039 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 9068 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 9447 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 9467 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 9528 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 9544 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 9673 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 10395 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 11254 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 11613 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 11632 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 12230 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 12268 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 12302 | `"/health", methods=["GET", "OPTIONS"]` |
| 12648 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 13293 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 13380 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 13439 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 13573 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 13616 | `"/code/stand", methods=["GET"]` |
| 13634 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 13659 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 13742 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 13824 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 13937 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 14038 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14135 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 14205 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14224 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14856 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 14921 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 16939 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 16962 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 16982 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 17065 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 17162 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 17197 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 17612 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 17617 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 17622 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 17627 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |

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
| 468 | MT5-Copier Panel-Proxy (Etappe 3, 15.08.2026) |
| 534 | Stack-Neustart per Knopf (15.08.2026, Finns Wunsch) |
| 626 | Duplikium Connect (Basic Auth → Token) |
| 724 | Duplikium Session-Handout (25.08.2026) |
| 771 | Duplikium Generic Proxy |
| 976 | Token Refresh |
| 1037 | Sessions überleben einen Backend-Neustart (17.09.2026) |
| 1182 | Mirror Control |
| 1229 | Mirror-Diagnose: Wer killt den Stream? (08.09.2026) |
| 1332 | Mirror Logic (Polling) TSX → MT5 |
| 1463 | TSX → MT5 Mirror, Echtzeit (SignalR statt Polling, 20.07.2026) |
| 2150 | NOTFALL-SL/TP für den Topstep-Mirror (17.09.2026) |
| 2402 | MT5 → TopstepX Mirror |
| 2716 | Duplikum-Rate-Budget (06.08.2026) |
| 3086 | Kurz-Caches für Login-Prüfung & Co. (01.10.2026, SUPABASE-DIÄT B) |
| 4062 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 4963 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 9831 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 9968 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 12295 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 12435 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 13587 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 14056 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 14150 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 14460 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 14758 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 15225 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 17684 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 17719 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (61229 Zeilen) und app.py._

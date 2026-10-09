# CODEMAP — Prophos

Automatisch erzeugt von `.claude/codemap.sh`. Nicht von Hand pflegen —
nach Aenderungen neu erzeugen: `bash .claude/codemap.sh`

> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine
> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen.
> Lesen z.B. mit `sed -n '13159,13400p' prophos.html` oder Read(offset/limit).

---

## prophos.html — Grobstruktur (65166 Zeilen)

| Bereich | Zeilen | Umfang |
|---|---|---|
| CSS (Hauptblock) | 25–6367 | 6343 |
| HTML-Markup (Views + Modals) | 6368–12474 | 6107 |
| **JS-Modul** (ein `<script type="module">`) | **12475–64870** | **52396** |
| Rest (CSS-/JS-Nachtrag) | 64871–65166 | 296 |

## prophos.html — JS-Sektionen (12475–64870)

Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.

| Zeilen | Umfang | Sektion |
|---|---|---|
| 12510–12539 | 30 | VIEW SWITCHER |
| 12540–12577 | 38 | BOOT |
| 12578–12874 | 297 | USER HYDRATION |
| 12875–12894 | 20 | LOGIN SCREEN SWITCHING (login / signup / reset) |
| 12895–12920 | 26 | BANNERS |
| 12921–12943 | 23 | LOGIN |
| 12944–12976 | 33 | SIGNUP |
| 12977–13001 | 25 | RESET |
| 13002–13021 | 20 | LOGOUT |
| 13022–13037 | 16 | USER DROPDOWN |
| 13038–18316 | 5279 | DASHBOARD TABS |
| 18317–18370 | 54 | HEDGE COSMOS SCROLL (Overview-Hero) |
| 18371–18668 | 298 | MOBILE SIDEBAR |
| 18669–18676 | 8 | DASHBOARD MOUNT |
| 18677–18945 | 269 | TOPSTEP MIRROR — TSX CONNECTION |
| 18946–19239 | 294 | DUPLIKUM CONNECTION |
| 19240–19504 | 265 | LOT RECHNER ⇢ DUPLIKIUM PUSH |
| 19505–19988 | 484 | TRADE-PLAN MODAL ⇢ DUPLIKIUM PUSH |
| 19989–20384 | 396 | DUPLIKUM LINKING (lokal) |
| 20385–22394 | 2010 | ENDE MT5-COPIER LINKING |
| 22395–23575 | 1181 | ENDE MT5-ROUTE |
| 23576–26250 | 2675 | ENDE ORBIT V2 |
| 26251–28467 | 2217 | ENDE FUSION-GEGENHEDGE |
| 28468–29885 | 1418 | ENDE MARKT LIVE |
| 29886–30016 | 131 | ENDE WINNING DAYS LIVE TRADES |
| 30017–30466 | 450 | ENDE DUP-ROUTE LIVE-LOTS |
| 30467–32406 | 1940 | DUPLIKUM AUTO-REFRESH |
| 32407–32493 | 87 | TRADE-COMPLETE: Status-Optionen |
| 32494–32808 | 315 | NACHFOLGER-WIZARD |
| 32809–32816 | 8 | ARCHIV-FILTER |
| 32817–35236 | 2420 | ACCOUNTS — SUPABASE CRUD |
| 35237–35989 | 753 | BULK ADD ACCOUNTS |
| 35990–35993 | 4 | END BULK ADD |
| 35994–36811 | 818 | TOPSTEP MIRROR — PAIR MAPPING |
| 36812–36871 | 60 | OVERVIEW & SIDEBAR HELPERS |
| 36872–37567 | 696 | ACCOUNTS — SUB-TABS, TSX-LISTE, VERLINKEN, SYNC |
| 37568–37715 | 148 | LOT RECHNER |
| 37716–56655 | 18940 | TRADE PLANS |
| 56656–57901 | 1246 | FINANZEN |
| 57902–64870 | 6969 | INITIAL LOAD: Accounts aus Supabase nach Login |

### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)

Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),
z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.

| Zeilen | Block |
|---|---|
| 12648–20612 | SPEICHER VOLL |
| 20613–20860 | UNTERBROCHENEN ECHO-V2-START ÜBERNEHMEN |
| 20861–20870 | V2-WEGE |
| 20871–20997 | PULS FÜR TOPSTEP |
| 20998–21338 | PC-KENNUNG VOM PANEL |
| 21339–22194 | FIRMEN-SCHLÜSSEL FÜR DEN RICHTUNGSSCHUTZ |
| 22195–22559 | ECHO V2 |
| 22560–22565 | MT5-BALANCE DAUERHAFT AM KONTO |
| 22566–22661 | SERVERNAME WIE BEWIESEN |
| 22662–22735 | MT5-BALANCE JETZT LESEN |
| 22736–22843 | BALANCE NACH JEDEM ECHO-TRADE |
| 22844–22849 | BALANCE JETZT LESEN |
| 22850–22973 | WARTESCHLANGE FÜR BALANCE-LESUNGEN |
| 22974–23018 | TOPSTEP V2 START-BASELINE AUS DER ORDER-ANTWORT |
| 23019–23336 | ORBIT V2 START-BASELINE AUS DER ORDER-ANTWORT |
| 23337–23423 | BALANCE-SPRUNG |
| 23424–23639 | P&L NACH DEM TRADE — DREI QUELLEN |
| 23640–23798 | P/L-EINGABE |
| 23799–24064 | LIQUIDATIONS-LEVEL STATT MASTER-SL |
| 24065–24131 | FUSION-P&L ÜBER ALLE VERSUCHE |
| 24132–24199 | PUFFER OHNE ECHTEN FILL |
| 24200–24398 | NACHZÜGLER NACH READER-ENDE |
| 24399–24437 | EINSTIEG AUS DEM PULS-FILL NACHTRAGEN |
| 24438–24504 | FRÜHER FUSION-HEDGE |
| 24505–24520 | PULS-ENDLESUNG |
| 24521–24557 | LOGIN-BREMSE |
| 24558–24728 | KONTO WEG |
| 24729–24782 | FOLGETRADE |
| 24783–25076 | KONTO-BEFUND PERSISTIEREN |
| 25077–25082 | DEMO-ENDE |
| 25083–25212 | HANDSTART-EINSTIEG |
| 25213–25403 | AUSSCHLAG-SCHUTZ |
| 25404–25443 | FEED-PUFFER FÜR DEN KLICKZEITPUNKT |
| 25444–25498 | TERMINAL-LEVEL AM ECHTEN TRADINGVIEW-FILL |
| 25499–25628 | HEDGE-REGELN VOR DEM RECHNEN |
| 25629–25699 | READER-STAND FÜR DEN HEDGE-WÄCHTER |
| 25700–25757 | SCHNELL-WÄCHTER |
| 25758–25815 | MASTER LAUT READER |
| 25816–26088 | END-BALANCE AUS DEM USERSCRIPT |
| 26089–26755 | MASTER-WEG-SCHUTZ SICHTBAR |
| 26756–26783 | EINSTIEGS-MARKER JE LAUFENDEM WINNING DAY |
| 26784–26932 | POSITIONS-ZONEN WIE IN TRADINGVIEW |
| 26933–27018 | BETRETEN |
| 27019–27034 | KANÄLE NUR, WO SIE GEBRAUCHT WERDEN |
| 27035–27152 | PC-TAB BRAUCHT DEN LIVE-KURS |
| 27153–27213 | FEED-DIAGNOSE |
| 27214–27352 | PLAN HEUTE NACHT |
| 27353–27432 | INLINE-BEARBEITUNG |
| 27433–27455 | PLAN NEU ANLEGEN |
| 27456–27478 | BALANCE JE KONTO |
| 27479–27774 | ZEITSTRAHL |
| 27775–27781 | ZUM ABHAKEN |
| 27782–28196 | ENDLESUNG SICHTBAR |
| 28197–28199 | ECHTER TP AUS TV |
| 28200–28487 | ECHTER ENTRY AUS TV |
| 28488–28596 | ECHO IM RADAR |
| 28597–28641 | PC-TAB-LEBENSZEICHEN JE ID |
| 28642–28827 | PC-TABS IM ADMIN |
| 28828–28861 | ABHAKEN OHNE ZURÜCKSPRINGEN |
| 28862–28899 | LIVE-P&L DES MASTER-KONTOS |
| 28900–28979 | SPANNE |
| 28980–28997 | ZIEL-SPANNE |
| 28998–29142 | HANDARBEIT |
| 29143–29193 | LÄUFT LIVE |
| 29194–29210 | WARTET |
| 29211–29251 | LESUNG VERLOREN |
| 29252–29280 | BLOW ERKENNEN |
| 29281–29310 | APEX-EVAL-SOFTBREACH |
| 29311–29338 | BESTANDEN-FLAG |
| 29339–29368 | ANSEHEN |
| 29369–31210 | MANUELLE ARBEIT |
| 31211–32351 | SUPABASE-DIÄT |
| 32352–32367 | ENTARCHIVIEREN ÜBERALL |
| 32368–33339 | ARCHIVIEREN MIT CLOUD-ABGLEICH |
| 33340–33477 | „Was noch geparkt werden soll" — die eigene Sicht auf den Kaufplan |
| 33478–33490 | AUTO-PLANER-CHIP |
| 33491–33598 | GRUND KURZ |
| 33599–33801 | LOGIN-ORT VOR DEM SIGNAL |
| 33802–35098 | KONTOWERT-SPALTE |
| 35099–38414 | ECHO NACH DER BULK-ANLAGE |
| 38415–38449 | SCHRITT STATT ART |
| 38450–40500 | KONTO-SPERRE VOR JEDEM START |
| 40501–41561 | ECHO V2 — Trade-Start ohne Hedge |
| 41562–42165 | RISIKO MASTER BEI WINNING DAY |
| 42166–42646 | NUR LAUFENDE ZÄHLEN |
| 42647–42913 | REMOTE-TRADE-SIGNALE |
| 42914–42938 | KONTO WEG BEIM START |
| 42939–43661 | FIRMEN-ABSTAND VOR JEDEM START |
| 43662–43688 | ECHO-V2-CHECKS NACHEINANDER |
| 43689–44321 | AUTO-START-WARTESCHLANGE |
| 44322–44480 | V2 SCHLIESSEN |
| 44481–44741 | PULS-ERGEBNISSE ÜBERNEHMEN |
| 44742 | ENDE V2 SCHLIESSEN |
| 44854–45358 | CLAIMS DIESES TABS MERKEN |
| 45359–45368 | LEERLAUF-TAKT DES EMPFÄNGERS |
| 45369–45457 | SUPABASE-DIÄT |
| 45458 | ENDE REMOTE-TRADE-SIGNALE |
| 45460–45704 | BENACHRICHTIGUNGEN AUFS HANDY |
| 45705 | ENDE BENACHRICHTIGUNGEN AUFS HANDY |
| 45707–45911 | AUTO-CLOSE VOR MARKET CLOSE |
| 45912–46086 | GEPLANTE STARTZEIT |
| 46087–46094 | NÄCHSTER PULS-EINSATZ |
| 46095–46278 | PULS LÄUFT GERADE |
| 46279–46382 | COUNTDOWN |
| 46383–46390 | SLAVE-VORPRÜFUNG VOR DEM WD-START |
| 46391–46448 | FUSION-MARGE |
| 46449–46586 | VORPRÜFLISTE |
| 46587–46695 | RICHTUNG AM START |
| 46696–46846 | START-FEHLER & NEU EINPLANEN |
| 46847–46860 | PULS-SPUR AM PLAN |
| 46861 | ENDE START-FEHLER |
| 46863–47131 | STARTZEIT-WARTESCHLANGE |
| 47132 | ENDE GEPLANTE STARTZEIT |
| 47134–47692 | AUTO-PLANER |
| 47693–47888 | EIN SCHALTER |
| 47889 | ENDE AUTO-PLANER |
| 47891–48108 | TRADE-PLANER-SEITE |
| 48109–48118 | ZEITSTRAHL V2 |
| 48119–48245 | PILLEN STATT KÜRZEL |
| 48246–48320 | NETTO-CHART |
| 48321–48382 | RISIKO NACH PUNKTEN |
| 48383–48446 | CHART-UMSCHALTER |
| 48447–48632 | KASTEN AM TRADE |
| 48633–48674 | BRAUCHT DICH |
| 48675–48799 | WAS TUN |
| 48800–49071 | ZIEL ERREICHT RAUS |
| 49072–49176 | BRAUCHT DICH NEU |
| 49177–49267 | RECHTE FÜR FREMDE VORSCHLÄGE |
| 49268–49357 | HYPO-P&L |
| 49358–49462 | HEUTE BEENDET |
| 49463–49523 | HYPO-P&L-CHART |
| 49524–49775 | BEENDET · BILANZ DES RECHNERS |
| 49776–49888 | MINI-POPUP TP · SL · GRÖSSE |
| 49889–49965 | STARTZEIT ÄNDERN |
| 49966–49980 | HYPO-BILANZ |
| 49981–49997 | KERZEN FÜR DEN HYPO-P&L-VERLAUF |
| 49998–50334 | BOOT-CACHE DER PLANER-SEITE |
| 50335 | ENDE TRADE-PLANER-SEITE |
| 50343 | ENDE AUTO-CLOSE |
| 51139–52177 | WINNING-DAY-FUSION-HEDGE IN DEN GESAMTKOSTEN |
| 52178–52334 | FUTURES VORPLANEN |
| 52335–52362 | TOPSTEP EXPRESS |
| 52363–52694 | KONTOGRÖSSE FÜR DIE ANZEIGE |
| 52695 | ENDE FUTURES VORPLANEN |
| 52697–52785 | WINNING-DAY-FARMER |
| 52786–52837 | ZEITFENSTER STATT TAKT |
| 52838–52897 | RICHTUNG ÜBERNEHMEN |
| 52898–52987 | BLÖCKE PER DRAG & DROP |
| 52988–53101 | RISIKO-RECHNUNG WIE DAS FORMULAR |
| 53102–53963 | SCHREIB-WÄCHTER FÜR OFFENE TABELLEN |
| 53964–54082 | ID OHNE NEU-WÜRFELN EINPLANEN |
| 54083–54834 | RICHTUNG PER KLICK |
| 54835–54899 | RISIKO MASTER FÜR ALLE WD-KONTEN |
| 54900 | ENDE WINNING-DAY-FARMER |
| 54902–55020 | WD-ANBAU |
| 55021 | ENDE WD-ANBAU |
| 57444–62252 | KONTO-AUSWAHL NACH PROP-FIRMA |
| 62253–62293 | BRÜCKEN-SCHUTZ |
| 62294–62314 | READER-DIREKTFEED |
| 62315–63114 | CODE-SCHLÜSSEL FÜRS PANEL |
| 63115–63121 | ADMIN „TRADE-PLANER" |
| 63122–63131 | NOTES-GEDÄCHTNIS |
| 63132–63165 | ADMIN-SICHT ERZWINGEN |
| 63166–63234 | BESTÄTIGEN OHNE WARTEN |
| 63235–63304 | ID-SICHT |
| 63305–63309 | ZU BESTÄTIGEN IM FIRMEN-BLOCK-DESIGN |
| 63310–63498 | DREI GRUPPEN |
| 63499–63717 | ID-DETAIL |
| 63718–63729 | BOT-SCHALTER IM ADMIN-REITER |
| 63730–63750 | LIVE-P&L IM ADMIN-REITER |
| 63751–63767 | SICHT-WÄCHTER |
| 63768 | ENDE ADMIN „TRADE-PLANER" |

### Untersektionen in den grossen Bloecken

Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:

| ab Zeile | Block |
|---|---|
| 30661 | LIVE TRADES — Aggregator für TopstepX + MetaApi + Duplikium |
| 31170 | AUTO TRADE TRACKER — simpel via getSlaveOrders |
| 31657 | MULTI-PROFIL-WÄCHTER — Trade-Ende auch für die NICHT aktiven Profile |
| 32079 | DASHBOARD — TODO-LISTE + RECENT TRADES |
| 32184 | ACCOUNT-ARCHIV & NACHFOLGER-CHAIN |
| 58014 | SUPABASE-SYNC für localStorage-Daten |
| 58237 | LOT-KALIBRIERUNG — Vergleichs-Trades zur Referenz-Firma |
| 58720 | FX-Kurs USD/EUR |
| 58888 | JOURNAL — Tägliche Trading-Notizen |
| 59182 | AI ADVISOR v2 — Chat-basierter Advisor mit Knowledge-Editor |
| 59546 | AI ADVISOR v5 — Conversations + Persistent Memory |
| 59808 | AI ADVISOR — TABS & FIRM RULES MANAGEMENT |

## prophos.html — Views und Modals (6368–12474)

Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.

| Zeile | Element |
|---|---|
| 6880 | view: **overview** |
| 6993 | view: **accounts** |
| 7326 | modal: linkTopstepModal |
| 7367 | view: **topstep** |
| 7464 | view: **calc** |
| 7592 | view: **trades** |
| 7761 | modal: tpVorplanModal |
| 7853 | modal: tplBestModal |
| 7869 | modal: apKontoModal |
| 7880 | modal: handModal |
| 7889 | modal: apProbeModal |
| 7911 | modal: tpOrderModal |
| 7993 | modal: tradePlanModal |
| 8382 | modal: tradeCompleteModal |
| 8490 | modal: successorModal |
| 8634 | modal: blownSummaryModal |
| 8671 | modal: tpPreflightModal |
| 8703 | modal: vcModal |
| 8739 | view: **risk** |
| 8757 | view: **advisor** |
| 8870 | modal: advisor-firm-modal |
| 8933 | modal: advisor-kb-modal |
| 8947 | modal: advisor-memory-modal |
| 8961 | modal: advisor-extract-modal |
| 8975 | view: **payouts** |
| 9214 | modal: finModal |
| 9301 | modal: finReceiveModal |
| 9332 | modal: finSettleModal |
| 9380 | view: **analytics** |
| 9398 | view: **journal** |
| 9486 | view: **account-detail** |
| 9535 | view: **livetrades** |
| 9568 | modal: linkDupModal |
| 9609 | modal: linkMt5Modal |
| 9650 | view: **managed** |
| 9741 | modal: mgSettleModal |
| 9788 | view: **notes** |
| 9808 | view: **news** |
| 9848 | view: **propbaum** |
| 9879 | view: **tplaner** |
| 9901 | view: **vorrat** |
| 9921 | view: **wdlive** |
| 9952 | view: **firmen** |
| 9998 | view: **markt** |
| 10068 | view: **mt5copier** |
| 10147 | view: **echoplus** |
| 10190 | modal: mtcAddModal |
| 10244 | view: **kasse** |
| 11602 | modal: walKommModal |
| 11648 | view: **settings** |
| 11779 | modal: customFirmModal |
| 11929 | modal: mwdErledigtModal |
| 11989 | modal: addAccountModal |
| 12296 | modal: credModal |
| 12313 | modal: bulkAddModal |

## app.py — Routen (24060 Zeilen)

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
| 3560 | `"/push/vapid-public", methods=["GET", "OPTIONS"]` |
| 3574 | `"/push/subscribe", methods=["POST", "OPTIONS"]` |
| 3606 | `"/push/unsubscribe", methods=["POST", "OPTIONS"]` |
| 3630 | `"/push/geraete", methods=["GET", "OPTIONS"]` |
| 3648 | `"/push/send", methods=["POST", "OPTIONS"]` |
| 3665 | `"/sw.js", methods=["GET"]` |
| 6595 | `"/admin/overview", methods=["GET", "OPTIONS"]` |
| 6891 | `"/admin/kapitel", methods=["GET", "OPTIONS"]` |
| 7078 | `"/admin/prop-baum", methods=["GET", "POST", "OPTIONS"]` |
| 7218 | `"/admin/auftrag", methods=["GET", "OPTIONS"]` |
| 7413 | `"/admin/vorrat", methods=["GET", "POST", "OPTIONS"]` |
| 9475 | `"/admin/vorrat/lauf", methods=["GET", "OPTIONS"]` |
| 9504 | `"/admin/vorrat/ki", methods=["POST", "OPTIONS"]` |
| 9883 | `"/admin/rechnung-daten", methods=["GET", "OPTIONS"]` |
| 9903 | `"/admin/rechnung", methods=["POST", "OPTIONS"]` |
| 9964 | `"/admin/rechnungen", methods=["GET", "OPTIONS"]` |
| 9980 | `"/admin/rechnung-pdf", methods=["GET", "OPTIONS"]` |
| 10110 | `"/admin/acc-plan", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 10934 | `"/admin/wd-heute", methods=["GET", "OPTIONS"]` |
| 11831 | `"/admin/live-trades", methods=["GET", "OPTIONS"]` |
| 12203 | `"/admin/pc-stand", methods=["GET", "OPTIONS"]` |
| 12325 | `"/admin/handarbeit", methods=["GET", "OPTIONS"]` |
| 12406 | `"/admin/wd-plaene", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` |
| 13048 | `"/admin/payout-calc", methods=["PATCH", "OPTIONS"]` |
| 13102 | `"/watcher/status", methods=["GET", "OPTIONS"]` |
| 13136 | `"/health", methods=["GET", "OPTIONS"]` |
| 13482 | `"/admin/kompass", methods=["GET", "OPTIONS"]` |
| 14127 | `"/reader-wacht/status", methods=["GET", "OPTIONS"]` |
| 14214 | `"/puls-diagnose/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14273 | `"/reader-diagnose/<kennung>", methods=["POST", "OPTIONS"]` |
| 14407 | `"/reader-feed-token", methods=["POST", "OPTIONS"]` |
| 14450 | `"/code/stand", methods=["GET"]` |
| 14468 | `"/code/datei/<path:pfad>", methods=["GET"]` |
| 14493 | `"/reader-kurs", methods=["POST", "OPTIONS"]` |
| 14576 | `"/admin/konten-pruefen", methods=["POST", "OPTIONS"]` |
| 14659 | `"/admin/bulk-vorlagen", methods=["POST", "OPTIONS"]` |
| 14788 | `"/admin/konto-balance-lesen", methods=["POST", "OPTIONS"]` |
| 14899 | `"/puls-inventar/<pc_id>", methods=["POST", "OPTIONS"]` |
| 14996 | `"/puls-regel/<pc_id>", methods=["GET", "OPTIONS"]` |
| 15066 | `"/puls-ergebnis/<pc_id>", methods=["POST", "OPTIONS"]` |
| 15085 | `"/puls-augen/<pc_id>", methods=["POST", "OPTIONS"]` |
| 16541 | `"/admin/kontowerte", methods=["GET", "OPTIONS"]` |
| 16674 | `"/admin/hypo-bilanz", methods=["GET", "OPTIONS"]` |
| 17374 | `"/account/entarchivieren", methods=["POST", "OPTIONS"]` |
| 21617 | `"/admin/auto-plan/delta", methods=["GET", "OPTIONS"]` |
| 21659 | `"/admin/auto-plan/ausgleichen", methods=["POST", "OPTIONS"]` |
| 21679 | `"/admin/auto-plan/ids", methods=["GET", "POST", "OPTIONS"]` |
| 22131 | `"/admin/auto-plan/plan", methods=["POST", "OPTIONS"]` |
| 22280 | `"/admin/auto-plan/start-protokoll", methods=["POST", "OPTIONS"]` |
| 22315 | `"/admin/auto-plan/ausgleich-einstellung", methods=["POST", "OPTIONS"]` |
| 23348 | `"/admin/auto-plan/bestaetigen", methods=["POST", "OPTIONS"]` |
| 23353 | `"/admin/auto-plan/zurueck", methods=["POST", "OPTIONS"]` |
| 23358 | `"/admin/auto-plan/loeschen", methods=["POST", "OPTIONS"]` |
| 23363 | `"/admin/auto-plan", methods=["GET", "POST", "OPTIONS"]` |
| 23738 | `"/admin/liquide", methods=["GET", "OPTIONS"]` |
| 23746 | `"/admin/liquide/abruf", methods=["POST", "OPTIONS"]` |
| 23761 | `"/admin/liquide/sheet", methods=["POST", "OPTIONS"]` |
| 23788 | `"/admin/liquide/sheet/aktiv", methods=["POST", "OPTIONS"]` |
| 23807 | `"/admin/liquide/kunde", methods=["POST", "OPTIONS"]` |

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
| 3205 | ADMIN-GRUPPEN (08.10.2026, Finn ~22:45 Dubai: „Emin bekommt seine Freunde als eigene IDs bei sich unter Admin … Ich sage in |
| 4285 | Statuswechsel-Wache fuer die Handy-Meldungen (23.09.2026) |
| 5248 | Gemessene Hedge-Quote aus der Hedge-Ära (24.09.2026, Finn zum Kontrafakt-Panel: „Es macht |
| 10268 | Farmer auf V2 (24.09.2026, Vollumstieg auf Kapitel „Ohne Hedge") |
| 10424 | Winning Days des Tages — Übersicht unter dem Markt-Chart (25.09.2026, Koordinations-Runde) |
| 13129 | /health (01.10.2026, AUSFALL-BREMSE): Railway hing am 30.09. mit, weil jeder Aufruf auf Supabase wartete; /version liest alle |
| 13269 | Auswertung (23.09.2026, Finn: „pack die Daten mal in Prophos, is der Bot von meinem Bruder, will |
| 14421 | CODE-QUELLE (07.10.2026, Finn: „man kann Prophos ja jetzt klauen" → Repo privat; Finn im Chat: „Code-Auslieferung über |
| 14917 | PULS-AUGEN über CDP (29.09.2026, Etappe E0, Finns Go) |
| 15011 | PULS-ERGEBNISSE (29.09.2026, Finns Live-Test 15:49–15:50 UTC, Plan 5ab15b24) |
| 15727 | KONTOWERT (06.10.2026, Finn: „das ist eins zu eins, wie es mit Gegenhedgen ist, und das ist eins zu eins der Betrag, |
| 16367 | KONTOWERT-SPALTE (07.10.2026, Finn: Kontowert ist seine neue Kennzahl — jedes Konto zeigt ihn in der normalen |
| 17551 | PROBELAUF ÜBER ALLE IDS (07.10.2026, Finn 04:08 dt: „Kannst du mal zum Test alle IDs einfach als geplant reinpacken, sodass ich |
| 19054 | SZENARIO-KURVE (08.10.2026, Finn 05:26 Dubai, Admin „Long 202 € · Short 376 € · Netto −174 € short", kurz davor +333: „Der Bot muss |
| 23861 | Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) |
| 23896 | Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) |

---

_Erzeugt aus prophos.html (65166 Zeilen) und app.py._

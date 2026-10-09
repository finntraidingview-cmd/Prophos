# Fragen der Routine „Puls-Fehler“ an Finn

Je Frage ein Block (siehe .claude/routinen/puls-fehler.md §6). Antworten einfach unter den Block schreiben.

## 2026-10-07 20:43 — kein_snapshot: nach 90 s kein frischer stand vom lese-ea
Was passiert: Am pc-2zc2we liefert der Lese-EA für das The5%ers-Konto (accounts-ID 362f73c3…) keinen frischen Stand — 2× heute (10:58 und 11:00 UTC), die Balance-Lesung bricht nach 90 s ab. Nur dieser PC, kein Code-Muster (am 01.10. je einmal pc-c8tka2 und pc-usq1i6, seitdem dort ruhig).
Was ich brauche: Am pc-2zc2we das MT5-Terminal dieses Kontos ansehen: ist es eingeloggt, hängt der Lese-EA (ProphosHedgeReader) im Chart, steht AutoTrading auf AN? Danach „✓ Behoben“ oder von Hand starten.
Stand 08.10. 20:39 (Routine): seit 07.10. 11:00 UTC kein neuer Fall auf diesem PC — bleibt offen, bis du es angesehen hast.
Status: offen

## 2026-10-07 20:43 — konto: konto # steht im dropdown 0× (nicht genau einmal) — anderer tradovate-login?
Was passiert: Am pc-2zc2we meldet sich Puls mit dem für die Firma hinterlegten Tradovate-Username an, das Zielkonto taucht in der Kontoliste aber 0× auf (05./06.10., Pläne 621cb106…, 1e4cabd3…, 14868bdb…, 4e6b6068…, 9e53f702…; am 02.10. einmal pc-l5o8bv, Plan e1c4d6d4…). Puls klickt dann richtigerweise nichts.
Was ich brauche: Eine Prüfung/Entscheidung: Gehört der in Einstellungen > Prop Firms hinterlegte Tradovate-Username wirklich zu dem Login, in dem diese Konten liegen? Falls eine Firma mehrere Tradovate-Logins hat, müsste der Username am Konto statt an der Firma hängen — das wäre eine Entscheidung von dir, kein Fix, den ich allein machen darf.
Stand 08.10. 20:39 (Routine): für Apex durch 6fd5a52 (Login-Beleg über die Kontonummer, scrollbare Liste) erledigt — seit dem Fix kein Fall. Offen bleibt nur der FundedNext-Fall vom 05.10. (pc-2zc2we, Username der Firma trifft das Konto nicht); seit 06.10. kein neuer Fall.
Status: offen

## 2026-10-08 05:40 — konto_balance: kein Tradovate-Username für die Firma (The5%ers)
Was passiert: Am pc-40mali wollte Puls heute 00:22 UTC die Balance eines The5%ers-Kontos (accounts-ID d4143916…) in TradingView lesen. Das Konto liegt nicht im gerade verbundenen Tradovate-Login, und für The5%ers ist kein Tradovate-Username hinterlegt — Puls kann den Login-Wechsel nicht selbst machen und bricht korrekt ab (nichts geklickt). Einzelfall, aber er kommt bei jeder Lesung/Order dieses Kontos wieder. Am selben PC lief um 00:04 UTC der Prophos-Tab nicht („Startzeit um 45 min verpasst“); der Plan startete 00:08 UTC dann doch — nur zur Kenntnis.
Was ich brauche: In Einstellungen > Prop Firms > The5%ers bearbeiten den „Tradovate-Username für TradingView“ eintragen (der Login, in dem dieses Konto liegt). Falls The5%ers-Futures-Konten bei dir nicht über Tradovate laufen, sag mir das — dann gehört das Konto nicht in die Tradovate-Lesung.
Antwort Finn (08.10.2026, über den Master): „Bei The5%ers ist CFD. Da gibt es keinen Tradovate-Nutzernamen.“
Erledigt (Slave 4, 08.10.2026): Ursache — das Konto hat keine mt5_links-Zeile, und „Balance lesen“ schickte jedes Nicht-Futures-Konto ohne MT5-Login in den Tradovate-Weg (konto_balance). Jetzt: app.py balance_lese_weg — Futures → konto_balance, CFD → mt5_balance (Login aus mt5_links, sonst die MT5-Nummer der External ID), CFD ohne Login → klare Meldung statt Tradovate; beide Wege (/admin/wd-plaene „balance“ und /admin/konto-balance-lesen). Im PC-Tab lehnt tvKontoBalanceJetzt CFD-Konten ab. Nichts mehr in den Prop-Firm-Einstellungen eintragen.
Status: erledigt

## 2026-10-08 20:39 — v2order: terminal-verbindung fehlgeschlagen (IPC timeout) — Windows-Abfrage offen
Was passiert: Am pc-c19p2l scheiterte der Echo-Start des FundingPips-Plans 840c8097… zweimal (13:42 und 14:16 UTC) mit „Terminal-Verbindung fehlgeschlagen (-10005, 'IPC timeout')“ — der Bot vermutet die Windows-Abfrage „Client Terminal …“ (MT5-Update / Benutzerkontensteuerung), die er nicht abnehmen darf. Der Plan steht noch auf „geplant“. Nur dieser PC. In mt5_live steht für diesen PC mt5_update.abgelehnt = true: die stille MT5-Update-Aufgabe (6ab30b9/4eeb949 von heute) wurde dort mit „Nein“ oder durch Zeitablauf nicht eingerichtet; dasselbe gilt für pc-auzre5, pc-pw1put und pc-xc5c52.
Was ich brauche: Am pc-c19p2l einmal nachsehen, ob eine Windows-Abfrage offen steht („Ja“), und im Echo-Panel „MT5-Update einrichten“ klicken bzw. die Windows-PowerShell-Abfrage einmal mit „Ja“ bestätigen — danach kommt die Abfrage nicht mehr und der Echo-Start läuft. Gelegentlich dasselbe auf pc-auzre5, pc-pw1put, pc-xc5c52 (dort bisher kein Fehlstart deswegen, aber „abgelehnt“). Danach Plan 840c8097… neu starten.
Stand 09.10. 05:45 (Routine): mt5_live zeigt mt5_update.abgelehnt = true weiterhin auf pc-c19p2l, pc-auzre5, pc-pw1put, pc-xc5c52; kein neuer IPC-Fall seit 14:16 UTC gestern, Plan 840c8097… steht noch „planned“.
Status: offen

## 2026-10-08 20:39 — orbit: slave-terminal (fusion-copier) nicht bereit — 'Algo Trading' im Hedge-Terminal nicht aktiv
Was passiert: Am pc-2zc2we meldete der Copier-Startcheck um 13:22 UTC (Plan 4ec590cb…): „'Algo Trading' ist im Hedge-Terminal nicht aktiv (Extras → Optionen → Expert Advisors). Aus Python nicht schaltbar.“ Puls hat richtigerweise nichts geklickt. Einmal; der Plan lief 3 min später über den lokalen Weg weiter und scheiterte dann an der TP-Einheit (von dir 13:36/13:48 UTC gefixt). Der Plan liegt nicht mehr in trade_plans (umgeplant/gelöscht?).
Was ich brauche: Am pc-2zc2we im Hedge-Terminal den Knopf „Algo Trading“ in der Werkzeugleiste einschalten (grün) bzw. Extras → Optionen → Expert Advisors → „Algorithmisches Handeln erlauben“ — sonst bricht der Copier dort bei jedem Fusion-Start ab. Falls das Hedge-Terminal auf diesem PC absichtlich ohne Algo Trading laufen soll, sag es mir, dann ist es keine Frage mehr.
Status: offen

## 2026-10-09 05:45 — drei Echo-Pläne stehen „planned“ mit verstrichener Startzeit
Was passiert: Drei Echo-Pläne haben gestern ihren Start nicht geschafft und stehen noch auf „planned“, ohne neuen Versuch: 72c2a073… (pc-auzre5, Start 13:57 UTC, Grund damals „MetaTrader5-Paket fehlt“ — seit 8032557 behoben), 840c8097… (pc-c19p2l, Start 14:12 UTC, IPC-Timeout / Windows-Abfrage, siehe Frage oben) und 1c3f7ecd… (pc-40mali, Start 23:47 UTC, FundedNext: Server „Trade disabled“, laut deiner Analyse ist das Konto serverseitig gesperrt — Kontostand an der Grenze). Puls hat überall richtig nichts weiter gemacht.
Was ich brauche: Eine Entscheidung je Plan — neu starten (72c2a073… sollte jetzt durchgehen), umplanen, oder löschen (1c3f7ecd…, wenn das Konto wirklich zu ist). Das kann ich nicht selbst: Pläne anfassen ist Finanz-/Planer-Logik.
Status: offen

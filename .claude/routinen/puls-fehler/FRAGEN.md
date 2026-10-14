# Fragen der Routine „Puls-Fehler“ an Finn

Je Frage ein Block (siehe .claude/routinen/puls-fehler.md §6). Antworten einfach unter den Block schreiben.

## 2026-10-07 20:43 — kein_snapshot: nach 90 s kein frischer stand vom lese-ea
Was passiert: Am pc-2zc2we liefert der Lese-EA für das The5%ers-Konto (accounts-ID 362f73c3…) keinen frischen Stand — 2× heute (10:58 und 11:00 UTC), die Balance-Lesung bricht nach 90 s ab. Nur dieser PC, kein Code-Muster (am 01.10. je einmal pc-c8tka2 und pc-usq1i6, seitdem dort ruhig).
Was ich brauche: Am pc-2zc2we das MT5-Terminal dieses Kontos ansehen: ist es eingeloggt, hängt der Lese-EA (ProphosHedgeReader) im Chart, steht AutoTrading auf AN? Danach „✓ Behoben“ oder von Hand starten.
Stand 08.10. 20:39 (Routine): seit 07.10. 11:00 UTC kein neuer Fall auf diesem PC — bleibt offen, bis du es angesehen hast.
Stand 10.10. 05:35 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 10.10. 20:37 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 11.10. 05:36 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 11.10. 20:37 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 12.10. 05:35 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 12.10. 20:35 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 13.10. 05:45 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 13.10. 23:07 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 14.10. 05:45 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Stand 14.10. 20:55 (Routine): weiterhin kein neuer Fall seit 07.10. 11:00 UTC.
Status: offen

## 2026-10-07 20:43 — konto: konto # steht im dropdown 0× (nicht genau einmal) — anderer tradovate-login?
Was passiert: Am pc-2zc2we meldet sich Puls mit dem für die Firma hinterlegten Tradovate-Username an, das Zielkonto taucht in der Kontoliste aber 0× auf (05./06.10., Pläne 621cb106…, 1e4cabd3…, 14868bdb…, 4e6b6068…, 9e53f702…; am 02.10. einmal pc-l5o8bv, Plan e1c4d6d4…). Puls klickt dann richtigerweise nichts.
Was ich brauche: Eine Prüfung/Entscheidung: Gehört der in Einstellungen > Prop Firms hinterlegte Tradovate-Username wirklich zu dem Login, in dem diese Konten liegen? Falls eine Firma mehrere Tradovate-Logins hat, müsste der Username am Konto statt an der Firma hängen — das wäre eine Entscheidung von dir, kein Fix, den ich allein machen darf.
Stand 08.10. 20:39 (Routine): für Apex durch 6fd5a52 (Login-Beleg über die Kontonummer, scrollbare Liste) erledigt — seit dem Fix kein Fall. Offen bleibt nur der FundedNext-Fall vom 05.10. (pc-2zc2we, Username der Firma trifft das Konto nicht); seit 06.10. kein neuer Fall.
Stand 10.10. 05:35 (Routine): kein neuer 0×-Fall. Verwandt, einmal: 09.10. 09:48 UTC pc-2zc2we, Plan d667b45e… — „Kein Konto-Umschalter zu sehen (aktiv '-') — auch nach dem Tradovate-Login“ (Tradeify-Username der Firma); nur zur Kenntnis, kein Code-Muster.
Stand 10.10. 20:37 (Routine): kein neuer Fall (heute Samstag, keine Orbit-Starts).
Stand 11.10. 05:36 (Routine): kein neuer Fall (Wochenende, keine Orbit-Starts seit 09.10. abends).
Stand 11.10. 20:37 (Routine): kein neuer Fall (Sonntag, keine Signale seit 10.10. 09:16 UTC).
Stand 12.10. 05:35 (Routine): kein neuer 0×-Fall (Montag 23:43 UTC lief die FundedNext-Lesung auf pc-2zc2we nach einem dritten Anlauf durch — Login-Abbruch, nicht 0×; dazu Fix .1458).
Stand 12.10. 20:35 (Routine): kein neuer 0×-Fall. Heute blockierte stattdessen 19× der TradingView-Dialog „Go ad-free. Everywhere“ das Abmelden (pc-2zc2we 09:51–13:02 UTC, pc-auzre5 14:40 UTC) — Fix .1468 (81a2a72) schließt ihn über sein X.
Stand 13.10. 05:45 (Routine): kein neuer 0×-Fall. Seit Fix .1468 (12.10. ~17:00 UTC) 0× „Go ad-free“ in 72 Signalen (ruhige Nacht, Orbit nur einmal auf pc-c19p2l).
Stand 13.10. 23:07 (Routine): 1 neuer Fall 13.10. 13:43 UTC auf pc-2zc2we (Endlesung: Ziel 0× auch nach dem Login mit dem Firmen-Username) — Einzelfall, bleibt offen.
Stand 14.10. 05:45 (Routine): kein neuer 0×-Fall. Verwandt, einmal: 14.10. 01:09 UTC pc-2zc2we, Balance-Lesung eines Tradeify-Kontos — Puls meldete den verbundenen FundedNext-Login ab, nahm den Firmen-Username TDFYU954… und TradingView meldete danach „Error! The login …“, 40 s kein Konto (Spur bei 2000 Zeichen abgeschnitten, der Rest der Meldung fehlt). Gleiche Frage wie oben: dieser eine Username soll drei verschiedene Tradeify-Konten erreichen (13.10. 13:43 UTC Ziel 0×) — liegen die wirklich alle in einem Tradovate-Login?
Stand 14.10. 20:55 (Routine): kein neuer 0×-Fall in TradingView. Verwandt, einmal in TopstepX: 14.10. 15:10 UTC pc-l5o8bv, Balance-Lesung EXPRESS-V2-682437-… — Ziel 0× in der Konto-Liste, alle gelisteten Konten dort „MAXIMUM_LOSS Violation“/„Ineligible“ (Geblowt-Auge .1535 greift, kein Puls-Fehler).
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
Stand 09.10. 20:45 (Routine): weiter „abgelehnt“ auf pc-c19p2l, pc-auzre5, pc-xc5c52 (pc-pw1put seit > 3 h ohne Meldung); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“ (zuletzt 16:20 UTC bearbeitet).
Stand 10.10. 05:35 (Routine): mt5_live 01:36 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52 (pc-pw1put seit > 6 h ohne Meldung); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“.
Stand 10.10. 20:37 (Routine): mt5_live 16:36 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52; pc-pw1put meldet seit 09.10. 00:08 UTC gar nicht mehr (> 40 h, PC aus?); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“.
Stand 11.10. 05:36 (Routine): mt5_live 01:35 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52; pc-pw1put meldet seit 09.10. 00:08 UTC nicht (> 49 h, PC aus?); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“.
Stand 11.10. 20:37 (Routine): mt5_live 16:35 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52; pc-pw1put meldet seit 09.10. 00:08 UTC nicht (> 64 h, PC aus?); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“.
Stand 12.10. 05:35 (Routine): mt5_live 01:36 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52; pc-pw1put meldet seit 09.10. 00:08 UTC nicht (> 73 h, PC aus?); kein neuer IPC-Fall; Plan 840c8097… steht noch „planned“.
Stand 12.10. 20:35 (Routine): **5 neue IPC-Fälle heute** auf pc-c19p2l (08:12, 08:34, 08:55, 09:16, 13:26 UTC, alle Plan 2aaec4c9…) — der Plan ging dann 13:51 UTC doch auf „open“ (Start von Hand?). mt5_live 16:36 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-xc5c52 und pc-pw1put (wieder da seit ~13:47 UTC). Plan 840c8097… steht noch „planned“. Die Windows-Abfrage auf pc-c19p2l kostet jetzt jeden Echo-Start dort — bitte einmal „Ja“ klicken bzw. die MT5-Update-Aufgabe einrichten.
Stand 13.10. 05:45 (Routine): kein neuer IPC-Fall seit 12.10. 13:26 UTC (nachts keine Echo-Starts auf pc-c19p2l). mt5_live 01:36 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-pw1put, pc-xc5c52. Plan 840c8097… steht noch „planned“.
Stand 13.10. 23:07 (Routine): IPC 13.10. 12:13 UTC auf pc-l5o8bv (dazu „IPC send failed“ 12:40 UTC dort), auf pc-c19p2l kein neuer IPC-Fall, aber 5× „F9-Dialog nicht gefunden“ (Plan 2070a993…, 10:35–12:58 UTC) — vermutlich dieselbe Ursache (offene Abfrage am Terminal), eigener Block unten. mt5_live 19:23 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-pw1put, pc-xc5c52. Plan 840c8097… steht noch „planned“.
Stand 14.10. 05:45 (Routine): kein neuer IPC-Fall seit 13.10. 12:13 UTC (nachts keine Echo-Starts). mt5_live 01:45 UTC weiter „abgelehnt“ auf pc-auzre5, pc-c19p2l, pc-pw1put, pc-xc5c52. Plan 840c8097… steht noch „planned“.
Stand 14.10. 20:55 (Routine): **1 neuer IPC-Fall auf einem weiteren PC**: 14.10. 14:25 UTC pc-usq1i6 (Plan 197b0714…), 1 min später dort „F9-Dialog nicht gefunden“ (Plan 6b950730…, Spur: Login-Dialog ‚Einloggen‘ übergangen) und 14:28 „Puls-Chrome kommt nicht in den Vordergrund“ (zweimal, Orbit-Plan 27e88673…) — passt zu einer offenen Windows-/MT5-Abfrage auf pc-usq1i6; alle drei Pläne stehen geparkt (Start 2027-01-01). Ab .1557 nennt die Spur das Fenster, das vorn liegt. mt5_live 16:37 UTC weiter „abgelehnt“ u. a. auf pc-pw1put und pc-xc5c52. Plan 840c8097… ist nicht mehr in trade_plans.
Stand 14.10. 20:55 (Routine): pc-c19p2l heute kein F9-Fall (Plan 2070a993… nicht mehr in trade_plans). **Neu auf pc-usq1i6**: 14:26 UTC Plan 6b950730…, 1 min nach dem IPC-Timeout dort (siehe Frage IPC) — gleiche Ursache vermutet: offene Windows-/MT5-Abfrage am Terminal von pc-usq1i6.
Status: offen

## 2026-10-08 20:39 — orbit: slave-terminal (fusion-copier) nicht bereit — 'Algo Trading' im Hedge-Terminal nicht aktiv
Was passiert: Am pc-2zc2we meldete der Copier-Startcheck um 13:22 UTC (Plan 4ec590cb…): „'Algo Trading' ist im Hedge-Terminal nicht aktiv (Extras → Optionen → Expert Advisors). Aus Python nicht schaltbar.“ Puls hat richtigerweise nichts geklickt. Einmal; der Plan lief 3 min später über den lokalen Weg weiter und scheiterte dann an der TP-Einheit (von dir 13:36/13:48 UTC gefixt). Der Plan liegt nicht mehr in trade_plans (umgeplant/gelöscht?).
Was ich brauche: Am pc-2zc2we im Hedge-Terminal den Knopf „Algo Trading“ in der Werkzeugleiste einschalten (grün) bzw. Extras → Optionen → Expert Advisors → „Algorithmisches Handeln erlauben“ — sonst bricht der Copier dort bei jedem Fusion-Start ab. Falls das Hedge-Terminal auf diesem PC absichtlich ohne Algo Trading laufen soll, sag es mir, dann ist es keine Frage mehr.
Stand 10.10. 05:35 (Routine): kein neuer Fall.
Stand 10.10. 20:37 (Routine): kein neuer Fall.
Stand 11.10. 05:36 (Routine): kein neuer Fall.
Stand 11.10. 20:37 (Routine): kein neuer Fall.
Stand 12.10. 05:35 (Routine): kein neuer Fall.
Stand 12.10. 20:35 (Routine): kein neuer Fall.
Stand 13.10. 05:45 (Routine): kein neuer Fall (seit .1494 prüft auch der Winning-Day-Weg auf Topstep vor dem Fusion-Hedge Algo Trading — dort heute Nacht kein Fehlstart).
Stand 13.10. 23:07 (Routine): kein neuer Fall.
Stand 14.10. 05:45 (Routine): kein neuer Fall.
Stand 14.10. 20:55 (Routine): kein neuer Fall.
Status: offen

## 2026-10-09 05:45 — drei Echo-Pläne stehen „planned“ mit verstrichener Startzeit
Was passiert: Drei Echo-Pläne haben gestern ihren Start nicht geschafft und stehen noch auf „planned“, ohne neuen Versuch: 72c2a073… (pc-auzre5, Start 13:57 UTC, Grund damals „MetaTrader5-Paket fehlt“ — seit 8032557 behoben), 840c8097… (pc-c19p2l, Start 14:12 UTC, IPC-Timeout / Windows-Abfrage, siehe Frage oben) und 1c3f7ecd… (pc-40mali, Start 23:47 UTC, FundedNext: Server „Trade disabled“, laut deiner Analyse ist das Konto serverseitig gesperrt — Kontostand an der Grenze). Puls hat überall richtig nichts weiter gemacht.
Was ich brauche: Eine Entscheidung je Plan — neu starten (72c2a073… sollte jetzt durchgehen), umplanen, oder löschen (1c3f7ecd…, wenn das Konto wirklich zu ist). Das kann ich nicht selbst: Pläne anfassen ist Finanz-/Planer-Logik.
Stand 09.10. 20:45 (Routine): 1c3f7ecd… ist aus trade_plans weg (erledigt); 72c2a073… (pc-auzre5) steht unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe Frage oben.
Stand 10.10. 05:35 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 10.10. 20:37 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 11.10. 05:36 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 11.10. 20:37 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 12.10. 05:35 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 12.10. 20:35 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben.
Stand 13.10. 05:45 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben. Dazu neu 72f456a4… (pc-xc5c52), siehe Frage vom 13.10.
Stand 13.10. 23:07 (Routine): 72c2a073… (pc-auzre5) unverändert „planned“ seit 08.10. 13:57 UTC; 840c8097… siehe oben; 72f456a4… (pc-xc5c52) heute 3× gescheitert (01:19 … 12:50 UTC), „planned“; neu dazu 2070a993… (pc-c19p2l, F9-Dialog, 5×), „planned“.
Stand 14.10. 05:45 (Routine): 72c2a073… (pc-auzre5) und 840c8097… (pc-c19p2l) unverändert „planned“; 72f456a4… (pc-xc5c52) und 2070a993… (pc-c19p2l) ebenfalls „planned“, kein neuer Versuch seit 13.10. 12:58 UTC.
Stand 14.10. 20:55 (Routine): 72c2a073…, 840c8097…, 72f456a4… und 2070a993… sind alle nicht mehr in trade_plans (gelöscht/umgeplant) — nichts mehr zu entscheiden; neue Einzelfälle laufen in den Fragen IPC, F9 und v2link weiter.
Status: erledigt

## 2026-10-12 20:35 — close: Position #287105476 (Plan eff62815…, pc-onkrbk) — zwei Close-Versuche ohne Erfolg, Plan steht noch „open“
Was passiert: Am pc-onkrbk scheiterte das Schließen der NDX100-Position des Plans eff62815… zweimal: 13:34 UTC „Close-Bot Timeout (300 s)“ (kein Trail), 14:07 UTC „Positions-Zeile #287105476 nicht gefunden (Zeilen-Scan ohne Treffer, 46 Punkte, 2× ausgegraut) — nichts geklickt“. Der Plan steht seit 08:53 UTC „open“ ohne Ende; in order_signale gibt es keinen dritten Versuch. Puls hat richtigerweise nichts blind geklickt — aber ich kann aus der Cloud nicht sehen, ob die Position noch offen ist oder schon (per TP/SL) zu war.
Was ich brauche: Im Master-Terminal auf pc-onkrbk nachsehen, ob #287105476 noch offen ist — wenn ja, von Hand schließen bzw. „Position schließen“ neu anstoßen; wenn nein, den Plan beenden. Danach sag mir bitte, ob die Position zum Zeitpunkt 14:07 UTC noch offen war: dann wäre der Zeilen-Scan das Problem (Code), sonst war es ein Nachzügler-Close und der Riegel hat richtig gehalten.
Stand 13.10. 05:45 (Routine): der Plan eff62815… steht seit 12.10. 17:15 UTC „completed“ (von dir beendet). Offen bleibt nur die Antwort: war die Position um 14:07 UTC noch offen (→ Zeilen-Scan des Close-Bots prüfen) oder schon zu (→ Riegel hat richtig gehalten)?
Stand 13.10. 23:07 (Routine): Antwort fehlt weiterhin (war die Position um 14:07 UTC noch offen?).
Stand 14.10. 05:45 (Routine): Antwort fehlt weiterhin (war die Position um 14:07 UTC noch offen?).
Stand 14.10. 20:55 (Routine): Antwort fehlt weiterhin (war die Position um 14:07 UTC noch offen?).
Status: offen

## 2026-10-12 20:35 — pc-na1q6b: pywinauto lädt nicht (win32ui-DLL) — vermutlich schon behoben, bitte bestätigen
Was passiert: Um 11:59 UTC brach ein Echo-Start auf pc-na1q6b (Plan eea942d0…) ab: „pywinauto ist da, lässt sich aber nicht laden: ImportError: DLL load failed while importing win32ui“ (Hinweis des Bots: VC++-Runtime fehlt oder Windows „Intelligente App-Steuerung“ blockt die DLL). Ab 13:25 UTC liefen auf demselben PC Echo-Orders durch (eea942d0… von Hand gestartet, abeac9f8… 14:13 UTC per Signal platziert) — also wurde dazwischen etwas gemacht. Nur dieser PC, kein Code-Muster.
Was ich brauche: Kurz bestätigen, dass die VC++-Runtime installiert bzw. die App-Steuerung aus ist (sonst kommt die Meldung nach dem nächsten Windows-Update wieder). Falls du nichts gemacht hast, sag es mir — dann beobachte ich den PC.
Stand 13.10. 05:45 (Routine): kein neuer Fall (nachts kein Echo-Start auf diesem PC).
Stand 13.10. 23:07 (Routine): kein neuer Fall.
Stand 14.10. 05:45 (Routine): kein neuer Fall.
Stand 14.10. 20:55 (Routine): kein neuer Fall auf pc-na1q6b (heute 15:37 UTC „pywinauto fehlt“ auf dem NEUEN pc-7ftp5l — eigene Frage unten).
Status: offen

## 2026-10-12 20:35 — Entscheidung: Tab lud während einer Echo-Order neu (pc-i8vyq8, 14:32 UTC) — Neulade-Wächter liegt außerhalb der Puls-Pfade
Was passiert: Plan 0c41fc25… (pc-i8vyq8) kam 14:32:35 UTC als Signal an; um 14:34 schloss der neu geladene Tab das Signal mit „⚠ Stand UNBEKANNT: Der Tab lud während einer Order neu“ ab (unklar). Der Plan startete trotzdem 14:33:39 UTC (Order lag, Plan heute von dir beendet, −968 $). Zeitlich passt das zum Sofort-Update auf .1466 (dein Push 14:17 UTC). Der Neulade-Wächter (bwGrund) soll bei „Signal in Arbeit“ / „Popup offen“ / „Start läuft“ warten — warum er hier doch lud (klassischer Echo-Weg route mt5 aus einem Signal?), kann ich nur im Wächter selbst prüfen, und der gehört nicht zu den Puls-Sektionen, die ich anfassen darf. Dazu am Morgen 08:50 UTC auf pc-onkrbk drei Balance-Lesungen „Tab neu geladen — Lesung abgebrochen“ ohne Push zu der Zeit.
Was ich brauche: Deine Entscheidung, ob ich den Neulade-Wächter (Sofort-Update, Brücken-Selbstheilung) für diesen Fall analysieren und ggf. den Ruhe-Check um den laufenden Echo-Preflight erweitern darf — oder ob du das selbst machst.
Stand 13.10. 05:45 (Routine): kein neuer Fall; deine Pushes .1469–.1497 (00:24–01:29 UTC) fielen in eine Phase ohne laufende Order — die Orders 00:26–01:26 UTC liefen alle durch.
Stand 13.10. 23:07 (Routine): kein neuer Fall (12.10. 14:32 UTC bleibt der einzige).
Stand 14.10. 05:45 (Routine): **1 neuer Fall** 13.10. 19:39 UTC auf pc-l5o8bv: close-Signal des Echo-Plans e6517192… — 19:38:41 „schon ein Bot-Lauf“ (ein Close lief bereits), 19:39:23 „Stand UNBEKANNT: Der Tab lud während einer Order neu“. Der Reload kam ~30 min nach deinen Pushes .1528/.1529 (19:08/19:09 UTC), also der aufgeschobene Sofort-Update-Reload — mitten im laufenden Close. Ausgang gut: Plan 19:41 UTC „completed“, Balance nachgelesen. Zweiter Beleg, dass der Wächter einen laufenden Close-Bot-Lauf nicht als „in Arbeit“ zählt. Entscheidung weiter offen.
Stand 14.10. 20:55 (Routine): kein neuer Fall.
Status: offen

## 2026-10-13 05:45 — v2link: Kein Master-Terminal für das FundedNext-100k-Konto auf pc-xc5c52 (Plan 72f456a4…)
Was passiert: Der Auto-Planer-Plan 72f456a4… (FundedNext 100k, „Phase 1 · Trading tage sammeln“, Mini-Trade 0,01 Lot) sollte 13.10. 01:19 UTC auf pc-xc5c52 starten. Der Start-Tick fand dort kein Master-Terminal für das Konto: „der Account braucht eine MT5-Verlinkung und eine Echo-Instanz mit Terminal-Pfad (Echo-Ansicht → Neue Instanz)“. Puls hat richtig nichts gemacht; der Plan steht „planned“ mit verstrichener Startzeit. Einrichtung, kein Code-Muster.
Was ich brauche: Auf pc-xc5c52 in der Echo-Ansicht eine Instanz mit Terminal-Pfad für dieses Konto anlegen und das Konto in MT5-Links verlinken — oder den Plan auf den PC legen, auf dem das Terminal dieses Kontos läuft. Danach den Plan neu starten (oder löschen, wenn das Konto dort nicht laufen soll).
Stand 13.10. 23:07 (Routine): 3 Fälle heute (01:19 … 12:50 UTC), Plan 72f456a4… weiter „planned“ — braucht deine Hand auf pc-xc5c52.
Stand 14.10. 05:45 (Routine): kein neuer Versuch, Plan 72f456a4… weiter „planned“ seit 13.10. 12:50 UTC.
Stand 14.10. 20:55 (Routine): **1 neuer Fall**: 14.10. 08:40 UTC, Plan 9709972c… (pc-xc5c52, FundedNext 100k), steht „planned“; 72f456a4… ist nicht mehr in trade_plans. Einrichtung auf pc-xc5c52 weiter offen.
Status: offen

## 2026-10-13 05:45 — close: Schließen in TopstepX gibt es noch nicht (Etappe K5) — Plan b7e026d4…, pc-l5o8bv
Was passiert: Um 01:23 UTC kam ein close-Signal für den Winning-Day-Plan b7e026d4… (TopstepX, pc-l5o8bv). Der Bot antwortet ehrlich: „Schließen in TopstepX kommt mit Etappe K5 — bitte in TopstepX von Hand schließen.“ Der Plan wurde 01:23:43 UTC beendet (von Hand). Jedes Schließen auf TopstepX landet so als Fehlstart in puls_fehler_muster, solange K5 fehlt — mit den Winning-Day-Plänen auf Topstep (seit .1488) werden das täglich mehrere.
Was ich brauche: Eine Entscheidung: Baust du K5 (Schließen über die Positions-Zeile in TopstepX, mit Beweis wie bei K4) selbst, oder soll die Routine es als Puls-Fix anfassen? Bis dahin führe ich diese Fälle nur im Bericht, nicht als Fehler.
Stand 13.10. 23:07 (Routine): 2 Fälle (01:23 + 02:04 UTC, Plan b7e026d4…, seit 01:23 „completed“) — weiter nur geführt, bis du entschieden hast.
Stand 14.10. 05:45 (Routine): kein neuer Fall (heute Nacht keine TopstepX-Signale).
Stand 14.10. 20:55 (Routine): kein neuer Fall.
Status: offen

## 2026-10-13 23:07 — v2order: F9-Dialog nicht gefunden — Abbruch, nichts gesendet (pc-c19p2l 5×, pc-l5o8bv 1×)
Was passiert: Auf pc-c19p2l brach der Echo-Start des Plans 2070a993… fünfmal ab (10:35, 10:58, 11:17, 11:40, 12:58 UTC): „Login/Lesen ok → Terminal betreten → F9-Dialog nicht gefunden“ — das Order-Fenster geht nach F9 nicht auf, Puls bricht richtig ab und sendet nichts. Derselbe PC hat seit dem 08.10. die offene Windows-/MT5-Abfrage (Frage oben, „abgelehnt“ in mt5_live); ein Terminal mit offener Systemabfrage nimmt keine Tastatur an. Einmal auch pc-l5o8bv (12:50 UTC, Plan 5065e12d…, Login/Lesen dort 33 s statt 1 s — Terminal war wohl gerade beschäftigt). Kein Code-Muster: ein PC wiederholt, der zweite einmal.
Was ich brauche: Am pc-c19p2l das Master-Terminal ansehen — steht eine Windows-/MT5-Abfrage offen („Ja“ klicken), ist das Terminal eingeloggt, geht F9 im Chart von Hand auf? Danach Plan 2070a993… neu starten oder umplanen.
Stand 14.10. 05:45 (Routine): kein neuer Fall seit 13.10. 12:58 UTC (nachts keine Echo-Starts auf pc-c19p2l); Plan 2070a993… weiter „planned“.
Status: offen

## 2026-10-13 23:07 — Google-Anzeige im Tradovate-Panel (dein Screenshot) — ohne „Close ad“ hat Puls kein X
Was passiert: Dein Screenshot zeigt unten links im Tradovate-Panel eine Google-Anzeige („Daily Options on EURO STOXX 50“) über der Positions-Tabelle. Puls schließt solche Kacheln nur über TradingViews eigenen Knopf „Close ad“ (heute 27× bewiesen weggeklickt, Order- und Balance-Weg, weil beide vor dem Konto-Schritt die Kachel prüfen). Zeigt die Kachel nur Googles Dreieck/X oben rechts, liegt das in Googles iframe — für Puls nicht lesbar, und ein blinder Klick dort öffnet eher „Stop seeing this ad“ als dass er schließt. Die Lesung selbst liest das DOM, die Anzeige verdeckt also keine Zahl; sie stört nur, wenn sie über dem Konto-Umschalter oder dem Kontextmenü liegt. Die Fehlstarts von heute kamen vom großen „Go ad-free. Everywhere“-Dialog — der ist mit .1530 gefixt (augen.js findet jetzt sein X).
Was ich brauche: Beim nächsten Mal mit der Maus über die Kachel fahren — erscheint ein kleines „Close ad“ (TradingViews X, nicht Googles Dreieck)? Wenn ja: Screenshot, dann prüfe ich, warum Puls es dort nicht findet. Wenn nein: kurz Bescheid — dann bleibt die Kachel stehen und ich sorge nur dafür, dass Puls darunter sauber weiterkommt.
Stand 14.10. 05:45 (Routine): heute Nacht 13× „Werbe-Kachel unten links geschlossen (ihr X, weg bewiesen)“ in 34 Signalen, dazu 1× der Dialog „Go ad-free. Everywhere“ über sein X geschlossen (23:24 UTC pc-40mali — Fix .1530 wirkt, seitdem 0× „kein eindeutiges X“). Antwort zum Google-Dreieck fehlt noch.
Stand 14.10. 20:55 (Routine): Antwort fehlt. Seit dem Morgenlauf 4× „Go ad-free. Everywhere“ über sein X geschlossen, 0× „kein eindeutiges X“ (Fix .1530 hält); Werbe-Kachel-Schließen in den Spuren weiter bewiesen.
Status: offen

## 2026-10-13 23:07 — zu_spaet: 35 verpasste Starts in 24 h, weil der Prophos-Tab am PC nicht lief (5 PCs)
Was passiert: 35 Ereignisse „Startzeit um # min verpasst — der Prophos-Tab am PC lief nicht“ (bis 167 min) auf pc-40mali, pc-auzre5, pc-c19p2l, pc-l5o8bv und pc-pw1put, letzter 14:53 UTC. Das ist kein Puls-Fehler — der Start-Tick läuft im Tab, und der Tab war zu bzw. der PC/Browser aus. Jeder dieser Starts wurde ohne Order nachgeholt oder verfiel.
Was ich brauche: Sollen auf diesen fünf PCs die Prophos-Tabs dauerhaft laufen (Autostart/Tab prüfen), oder ist es gewollt, dass dort tagsüber kein Tab läuft? Im zweiten Fall führe ich das Muster nur noch, ohne es zu zählen.
Stand 14.10. 05:45 (Routine): 1 neuer Fall (pc-usq1i6 14.10. 01:15 UTC, 34 min; Plan a6b05461… lief 01:18 UTC durch). Gestern tags gesamt: 25× pc-c19p2l (bis 99 min), 6× pc-auzre5 (bis 722 min), je 1× pc-40mali, pc-l5o8bv, pc-pw1put. Entscheidung offen.
Stand 14.10. 20:55 (Routine): **21 neue Fälle** seit 01:45 UTC: 15× pc-c19p2l (bis 369 min), je 2× pc-l5o8bv (bis 77 min) und pc-xc5c52 (bis 300 min), 1× pc-pw1put (566 min), 1× pc-usq1i6 (96 min). Entscheidung offen.
Antwort Master 14.10. 23:30 (Finn: „alle Puls-Fehler beheben"): Die Meldung war fast immer FALSCH, kein PC-Thema. Der Tab rechnete mit seinem alten start_um (Pläne ohne Realtime); der Bot hatte den Start vorgezogen (18:22 „72 min verpasst", DB-Start 18:27), Winning Days hatten Start 16:30 und wurden um 11:20 als „60 min verpasst" gemeldet, geparkte Puls-Pause-Pläne (Start 2027) ebenso. Fix .1558: vor jedem „verpasst"-Claim liest der Tab start_um/status/claim frisch aus der DB; weicht es ab oder liegt in der Zukunft → lokalen Plan nachziehen, kein Claim, keine Meldung. Routine: Muster nach .1558 beobachten; nur Fälle, in denen der DB-Start wirklich verstrichen war, zählen noch.
Status: erledigt

## 2026-10-14 05:45 — ticket: 'Take profit' steht nicht auf $ (Einheit 'price') — pc-t8wg97 (neuer PC)
Was passiert: Erste Orbit-Order auf pc-t8wg97 (14.10. 00:09 UTC, Plan 0018b690…, Tradeify): das Order-Ticket in TradingView stand bei Take profit auf „price“ (Beschriftung „Take profit price“) — Puls hat richtig nichts gesendet, der Wert 23 wäre dort ein Kurs gewesen. 45 s später lief die Wiederholung durch, da stand das Feld auf $ (von Hand umgestellt?). Dieselbe Einheit-Sache gab es 02.10. 4× auf pc-xc5c52. Puls stellt die Einheit bewusst nicht selbst um.
Was ich brauche: Im Puls-Chrome auf pc-t8wg97 im Order-Ticket die Einheit bei Take profit UND Stop loss einmal auf $ stellen (der ▾-Wähler neben der Beschriftung) — TradingView merkt sich das je Browser-Profil, danach kommt der Fehler dort nicht mehr. Oder eine Entscheidung: soll Puls die Einheit selbst auf $ umstellen (Klick auf den Wähler, Beweis durch Rücklesung der Beschriftung)? Das wäre ein neuer Handgriff im Ticket, den ich nur mit deinem Ja baue.
Stand 14.10. 20:55 (Routine): kein neuer Fall auf pc-t8wg97 (keine weitere Orbit-Order dort seit 00:10 UTC).
Antwort Master 14.10. 23:30 (Finn: „alle Puls-Fehler beheben"): Puls stellt die Einheit selbst auf $ um — Klick auf den ▾-Wähler neben „Take profit"/„Stop loss", Beweis durch Rücklesung der Beschriftung („Take profit $"), sonst Abbruch wie bisher. Gilt für jeden PC, nicht nur pc-t8wg97.
Status: erledigt

## 2026-10-14 20:55 — start: pywinauto fehlt (nur auf dem PC lauffähig) — pc-7ftp5l (neuer PC)
Was passiert: Der erste Echo-Start auf dem neuen pc-7ftp5l (14.10. 15:37 UTC, Plan 38c7a6f1…) brach sofort ab: „pywinauto fehlt (nur auf dem PC lauffaehig)“ — das Python auf diesem PC hat das Paket nicht, der Bot kann dort weder Terminal noch Fenster bedienen. Keine Order, Plan bleibt „planned“. Einrichtung, kein Code.
Was ich brauche: Auf pc-7ftp5l einmal die Einrichtung nachziehen (start-alles.bat / Paket-Installation wie auf den anderen PCs: pywinauto + MetaTrader5 im Python des Bots), danach den Plan 38c7a6f1… neu starten.
Status: offen

## 2026-10-14 20:55 — pc: lokales Backend nicht erreichbar (TypeError: Failed to fetch) — pc-40mali
Was passiert: Zwei Orbit-Starts auf pc-40mali (14.10. 14:16 und 14:23 UTC, Pläne c255d9e7… und 4fdc2c82…) kamen nicht bis zum Bot: der Prophos-Tab erreichte das lokale Backend (panel.py) nicht — „Failed to fetch“. Beide Pläne stehen „planned“ mit verstrichener Startzeit. mt5_live meldete von diesem PC um 16:37 UTC wieder frisch (Bot .1556), das Panel läuft also inzwischen oder wieder. Ein PC, zwei Fälle in 7 min.
Was ich brauche: Kurz prüfen, ob auf pc-40mali das Panel (start-panel.bat / Autostart) dauerhaft läuft oder um 14:16 UTC neu gestartet wurde — und die beiden Pläne neu starten oder umplanen.
Antwort Master 14.10. 23:30: Einrichtung pc-40mali, Finn prüft den Panel-Autostart. Code: der Tab soll bei „Failed to fetch" den Start nicht als verpasst verbrauchen, sondern 2–5 min warten und erneut versuchen (Backend kommt beim Neustart wieder) — in der nächsten Routine bauen, falls nicht schon so.
Status: erledigt

## 2026-10-14 20:55 — Entscheidung: Ticket nimmt nach dem Konto-Wechsel keine Eingabe an (4 Fälle/24 h, 4 PCs) — Ticket neu öffnen?
Was passiert: 13.10. 23:11 UTC pc-40mali und 14.10. 12:41 pc-pw1put: „Seite steht nicht auf SELL ('Buy 3 NQZ6 MARKET', 3 Versuche)“; 14.10. 05:46 pc-c19p2l „Units stehen nicht auf 4 (Feld: '5')“ und 13:10 pc-xc5c52 „Units stehen nicht auf 2 (Feld: '3')“. Alle vier direkt nach einem Konto-Wechsel im Panel; Hover, Fenster am Punkt und Feld-Fokus waren bewiesen, Klick und Getipptes kamen trotzdem nicht an — und im Ticket stand jedes Mal GENAU die Menge der vorigen Order dieses PCs (5, 3, 3, 3). Dein Pfeil-Weg .1550 („genau ±1 → ein Pfeil“) geht von einer Rundung aus; die „+1“ war der Vorgänger-Wert — der Pfeil kann in diesem Fall nichts richten (schadet aber auch nicht: Fokus-Beweis, höchstens ein Pfeil). Minuten später lief derselbe Plan durch (pc-pw1put 12:59 ohne Konto-Wechsel; pc-40mali 23:31 nach Shift+T mit frischem Ticket). 146 andere Konto-Wechsel in 7 Tagen liefen durch — es ist also kein fester Zustand, sondern ein „taubes“ Ticket für eine Weile. Ab .1557 schreibt der Bot beim Abbruch eine Diagnose-Zeile in die Spur (oberstes Element am Punkt, disabled/aria-busy auf dem Weg nach oben, Seiten-Fokus, aktives Element, offene Dialoge).
Was ich brauche: Eine Entscheidung, bevor ich mehr baue: (a) erst die Diagnose-Zeilen der nächsten Fälle abwarten (mein Vorschlag — ein bis zwei Tage), oder (b) jetzt den Handgriff bauen „nimmt das Ticket nach einem Konto-Wechsel die bewiesene Eingabe nicht an → Ticket per Shift+T zu und wieder auf (Chart-Klick für den Fokus, Beweis ticket.da weg → da), dann einmal neu“ — das wäre ein neuer Schritt im Ticket, den ich nur mit deinem Ja baue. Und: soll der Pfeil-Weg .1550 bleiben?
Antwort Master 14.10. 23:30 (Finn: „alle Puls-Fehler beheben"): (b) JETZT bauen. Nimmt das Ticket nach einem Konto-Wechsel die bewiesene Eingabe nicht an (Seite oder Units stehen nach dem Tipp/Klick noch auf dem Vorgänger-Wert), dann Ticket per Shift+T zu und wieder auf (Chart-Klick für den Fokus, Beweis ticket.da weg → da), danach genau EIN neuer Durchlauf mit allen Beweisen wie bisher. Riegel unverändert: ohne Beweis kein Klick auf den Kauf-Knopf. Die Diagnose-Zeile aus .1557 bleibt in der Spur.
Status: erledigt

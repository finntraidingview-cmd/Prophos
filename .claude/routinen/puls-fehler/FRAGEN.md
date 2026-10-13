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
Status: offen

## 2026-10-12 20:35 — close: Position #287105476 (Plan eff62815…, pc-onkrbk) — zwei Close-Versuche ohne Erfolg, Plan steht noch „open“
Was passiert: Am pc-onkrbk scheiterte das Schließen der NDX100-Position des Plans eff62815… zweimal: 13:34 UTC „Close-Bot Timeout (300 s)“ (kein Trail), 14:07 UTC „Positions-Zeile #287105476 nicht gefunden (Zeilen-Scan ohne Treffer, 46 Punkte, 2× ausgegraut) — nichts geklickt“. Der Plan steht seit 08:53 UTC „open“ ohne Ende; in order_signale gibt es keinen dritten Versuch. Puls hat richtigerweise nichts blind geklickt — aber ich kann aus der Cloud nicht sehen, ob die Position noch offen ist oder schon (per TP/SL) zu war.
Was ich brauche: Im Master-Terminal auf pc-onkrbk nachsehen, ob #287105476 noch offen ist — wenn ja, von Hand schließen bzw. „Position schließen“ neu anstoßen; wenn nein, den Plan beenden. Danach sag mir bitte, ob die Position zum Zeitpunkt 14:07 UTC noch offen war: dann wäre der Zeilen-Scan das Problem (Code), sonst war es ein Nachzügler-Close und der Riegel hat richtig gehalten.
Stand 13.10. 05:45 (Routine): der Plan eff62815… steht seit 12.10. 17:15 UTC „completed“ (von dir beendet). Offen bleibt nur die Antwort: war die Position um 14:07 UTC noch offen (→ Zeilen-Scan des Close-Bots prüfen) oder schon zu (→ Riegel hat richtig gehalten)?
Stand 13.10. 23:07 (Routine): Antwort fehlt weiterhin (war die Position um 14:07 UTC noch offen?).
Status: offen

## 2026-10-12 20:35 — pc-na1q6b: pywinauto lädt nicht (win32ui-DLL) — vermutlich schon behoben, bitte bestätigen
Was passiert: Um 11:59 UTC brach ein Echo-Start auf pc-na1q6b (Plan eea942d0…) ab: „pywinauto ist da, lässt sich aber nicht laden: ImportError: DLL load failed while importing win32ui“ (Hinweis des Bots: VC++-Runtime fehlt oder Windows „Intelligente App-Steuerung“ blockt die DLL). Ab 13:25 UTC liefen auf demselben PC Echo-Orders durch (eea942d0… von Hand gestartet, abeac9f8… 14:13 UTC per Signal platziert) — also wurde dazwischen etwas gemacht. Nur dieser PC, kein Code-Muster.
Was ich brauche: Kurz bestätigen, dass die VC++-Runtime installiert bzw. die App-Steuerung aus ist (sonst kommt die Meldung nach dem nächsten Windows-Update wieder). Falls du nichts gemacht hast, sag es mir — dann beobachte ich den PC.
Stand 13.10. 05:45 (Routine): kein neuer Fall (nachts kein Echo-Start auf diesem PC).
Stand 13.10. 23:07 (Routine): kein neuer Fall.
Status: offen

## 2026-10-12 20:35 — Entscheidung: Tab lud während einer Echo-Order neu (pc-i8vyq8, 14:32 UTC) — Neulade-Wächter liegt außerhalb der Puls-Pfade
Was passiert: Plan 0c41fc25… (pc-i8vyq8) kam 14:32:35 UTC als Signal an; um 14:34 schloss der neu geladene Tab das Signal mit „⚠ Stand UNBEKANNT: Der Tab lud während einer Order neu“ ab (unklar). Der Plan startete trotzdem 14:33:39 UTC (Order lag, Plan heute von dir beendet, −968 $). Zeitlich passt das zum Sofort-Update auf .1466 (dein Push 14:17 UTC). Der Neulade-Wächter (bwGrund) soll bei „Signal in Arbeit“ / „Popup offen“ / „Start läuft“ warten — warum er hier doch lud (klassischer Echo-Weg route mt5 aus einem Signal?), kann ich nur im Wächter selbst prüfen, und der gehört nicht zu den Puls-Sektionen, die ich anfassen darf. Dazu am Morgen 08:50 UTC auf pc-onkrbk drei Balance-Lesungen „Tab neu geladen — Lesung abgebrochen“ ohne Push zu der Zeit.
Was ich brauche: Deine Entscheidung, ob ich den Neulade-Wächter (Sofort-Update, Brücken-Selbstheilung) für diesen Fall analysieren und ggf. den Ruhe-Check um den laufenden Echo-Preflight erweitern darf — oder ob du das selbst machst.
Stand 13.10. 05:45 (Routine): kein neuer Fall; deine Pushes .1469–.1497 (00:24–01:29 UTC) fielen in eine Phase ohne laufende Order — die Orders 00:26–01:26 UTC liefen alle durch.
Stand 13.10. 23:07 (Routine): kein neuer Fall (12.10. 14:32 UTC bleibt der einzige).
Status: offen

## 2026-10-13 05:45 — v2link: Kein Master-Terminal für das FundedNext-100k-Konto auf pc-xc5c52 (Plan 72f456a4…)
Was passiert: Der Auto-Planer-Plan 72f456a4… (FundedNext 100k, „Phase 1 · Trading tage sammeln“, Mini-Trade 0,01 Lot) sollte 13.10. 01:19 UTC auf pc-xc5c52 starten. Der Start-Tick fand dort kein Master-Terminal für das Konto: „der Account braucht eine MT5-Verlinkung und eine Echo-Instanz mit Terminal-Pfad (Echo-Ansicht → Neue Instanz)“. Puls hat richtig nichts gemacht; der Plan steht „planned“ mit verstrichener Startzeit. Einrichtung, kein Code-Muster.
Was ich brauche: Auf pc-xc5c52 in der Echo-Ansicht eine Instanz mit Terminal-Pfad für dieses Konto anlegen und das Konto in MT5-Links verlinken — oder den Plan auf den PC legen, auf dem das Terminal dieses Kontos läuft. Danach den Plan neu starten (oder löschen, wenn das Konto dort nicht laufen soll).
Stand 13.10. 23:07 (Routine): 3 Fälle heute (01:19 … 12:50 UTC), Plan 72f456a4… weiter „planned“ — braucht deine Hand auf pc-xc5c52.
Status: offen

## 2026-10-13 05:45 — close: Schließen in TopstepX gibt es noch nicht (Etappe K5) — Plan b7e026d4…, pc-l5o8bv
Was passiert: Um 01:23 UTC kam ein close-Signal für den Winning-Day-Plan b7e026d4… (TopstepX, pc-l5o8bv). Der Bot antwortet ehrlich: „Schließen in TopstepX kommt mit Etappe K5 — bitte in TopstepX von Hand schließen.“ Der Plan wurde 01:23:43 UTC beendet (von Hand). Jedes Schließen auf TopstepX landet so als Fehlstart in puls_fehler_muster, solange K5 fehlt — mit den Winning-Day-Plänen auf Topstep (seit .1488) werden das täglich mehrere.
Was ich brauche: Eine Entscheidung: Baust du K5 (Schließen über die Positions-Zeile in TopstepX, mit Beweis wie bei K4) selbst, oder soll die Routine es als Puls-Fix anfassen? Bis dahin führe ich diese Fälle nur im Bericht, nicht als Fehler.
Stand 13.10. 23:07 (Routine): 2 Fälle (01:23 + 02:04 UTC, Plan b7e026d4…, seit 01:23 „completed“) — weiter nur geführt, bis du entschieden hast.
Status: offen

## 2026-10-13 23:07 — v2order: F9-Dialog nicht gefunden — Abbruch, nichts gesendet (pc-c19p2l 5×, pc-l5o8bv 1×)
Was passiert: Auf pc-c19p2l brach der Echo-Start des Plans 2070a993… fünfmal ab (10:35, 10:58, 11:17, 11:40, 12:58 UTC): „Login/Lesen ok → Terminal betreten → F9-Dialog nicht gefunden“ — das Order-Fenster geht nach F9 nicht auf, Puls bricht richtig ab und sendet nichts. Derselbe PC hat seit dem 08.10. die offene Windows-/MT5-Abfrage (Frage oben, „abgelehnt“ in mt5_live); ein Terminal mit offener Systemabfrage nimmt keine Tastatur an. Einmal auch pc-l5o8bv (12:50 UTC, Plan 5065e12d…, Login/Lesen dort 33 s statt 1 s — Terminal war wohl gerade beschäftigt). Kein Code-Muster: ein PC wiederholt, der zweite einmal.
Was ich brauche: Am pc-c19p2l das Master-Terminal ansehen — steht eine Windows-/MT5-Abfrage offen („Ja“ klicken), ist das Terminal eingeloggt, geht F9 im Chart von Hand auf? Danach Plan 2070a993… neu starten oder umplanen.
Status: offen

## 2026-10-13 23:07 — Google-Anzeige im Tradovate-Panel (dein Screenshot) — ohne „Close ad“ hat Puls kein X
Was passiert: Dein Screenshot zeigt unten links im Tradovate-Panel eine Google-Anzeige („Daily Options on EURO STOXX 50“) über der Positions-Tabelle. Puls schließt solche Kacheln nur über TradingViews eigenen Knopf „Close ad“ (heute 27× bewiesen weggeklickt, Order- und Balance-Weg, weil beide vor dem Konto-Schritt die Kachel prüfen). Zeigt die Kachel nur Googles Dreieck/X oben rechts, liegt das in Googles iframe — für Puls nicht lesbar, und ein blinder Klick dort öffnet eher „Stop seeing this ad“ als dass er schließt. Die Lesung selbst liest das DOM, die Anzeige verdeckt also keine Zahl; sie stört nur, wenn sie über dem Konto-Umschalter oder dem Kontextmenü liegt. Die Fehlstarts von heute kamen vom großen „Go ad-free. Everywhere“-Dialog — der ist mit .1530 gefixt (augen.js findet jetzt sein X).
Was ich brauche: Beim nächsten Mal mit der Maus über die Kachel fahren — erscheint ein kleines „Close ad“ (TradingViews X, nicht Googles Dreieck)? Wenn ja: Screenshot, dann prüfe ich, warum Puls es dort nicht findet. Wenn nein: kurz Bescheid — dann bleibt die Kachel stehen und ich sorge nur dafür, dass Puls darunter sauber weiterkommt.
Status: offen

## 2026-10-13 23:07 — zu_spaet: 35 verpasste Starts in 24 h, weil der Prophos-Tab am PC nicht lief (5 PCs)
Was passiert: 35 Ereignisse „Startzeit um # min verpasst — der Prophos-Tab am PC lief nicht“ (bis 167 min) auf pc-40mali, pc-auzre5, pc-c19p2l, pc-l5o8bv und pc-pw1put, letzter 14:53 UTC. Das ist kein Puls-Fehler — der Start-Tick läuft im Tab, und der Tab war zu bzw. der PC/Browser aus. Jeder dieser Starts wurde ohne Order nachgeholt oder verfiel.
Was ich brauche: Sollen auf diesen fünf PCs die Prophos-Tabs dauerhaft laufen (Autostart/Tab prüfen), oder ist es gewollt, dass dort tagsüber kein Tab läuft? Im zweiten Fall führe ich das Muster nur noch, ohne es zu zählen.
Status: offen

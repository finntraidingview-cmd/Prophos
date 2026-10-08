# Fragen der Routine „Puls-Fehler“ an Finn

Je Frage ein Block (siehe .claude/routinen/puls-fehler.md §6). Antworten einfach unter den Block schreiben.

## 2026-10-07 20:43 — kein_snapshot: nach 90 s kein frischer stand vom lese-ea
Was passiert: Am pc-2zc2we liefert der Lese-EA für das The5%ers-Konto (accounts-ID 362f73c3…) keinen frischen Stand — 2× heute (10:58 und 11:00 UTC), die Balance-Lesung bricht nach 90 s ab. Nur dieser PC, kein Code-Muster (am 01.10. je einmal pc-c8tka2 und pc-usq1i6, seitdem dort ruhig).
Was ich brauche: Am pc-2zc2we das MT5-Terminal dieses Kontos ansehen: ist es eingeloggt, hängt der Lese-EA (ProphosHedgeReader) im Chart, steht AutoTrading auf AN? Danach „✓ Behoben“ oder von Hand starten.
Status: offen

## 2026-10-07 20:43 — konto: konto # steht im dropdown 0× (nicht genau einmal) — anderer tradovate-login?
Was passiert: Am pc-2zc2we meldet sich Puls mit dem für die Firma hinterlegten Tradovate-Username an, das Zielkonto taucht in der Kontoliste aber 0× auf (05./06.10., Pläne 621cb106…, 1e4cabd3…, 14868bdb…, 4e6b6068…, 9e53f702…; am 02.10. einmal pc-l5o8bv, Plan e1c4d6d4…). Puls klickt dann richtigerweise nichts.
Was ich brauche: Eine Prüfung/Entscheidung: Gehört der in Einstellungen > Prop Firms hinterlegte Tradovate-Username wirklich zu dem Login, in dem diese Konten liegen? Falls eine Firma mehrere Tradovate-Logins hat, müsste der Username am Konto statt an der Firma hängen — das wäre eine Entscheidung von dir, kein Fix, den ich allein machen darf.
Status: offen

## 2026-10-08 05:40 — konto_balance: kein Tradovate-Username für die Firma (The5%ers)
Was passiert: Am pc-40mali wollte Puls heute 00:22 UTC die Balance eines The5%ers-Kontos (accounts-ID d4143916…) in TradingView lesen. Das Konto liegt nicht im gerade verbundenen Tradovate-Login, und für The5%ers ist kein Tradovate-Username hinterlegt — Puls kann den Login-Wechsel nicht selbst machen und bricht korrekt ab (nichts geklickt). Einzelfall, aber er kommt bei jeder Lesung/Order dieses Kontos wieder. Am selben PC lief um 00:04 UTC der Prophos-Tab nicht („Startzeit um 45 min verpasst“); der Plan startete 00:08 UTC dann doch — nur zur Kenntnis.
Was ich brauche: In Einstellungen > Prop Firms > The5%ers bearbeiten den „Tradovate-Username für TradingView“ eintragen (der Login, in dem dieses Konto liegt). Falls The5%ers-Futures-Konten bei dir nicht über Tradovate laufen, sag mir das — dann gehört das Konto nicht in die Tradovate-Lesung.
Antwort Finn (08.10.2026, über den Master): „Bei The5%ers ist CFD. Da gibt es keinen Tradovate-Nutzernamen.“
Erledigt (Slave 4, 08.10.2026): Ursache — das Konto hat keine mt5_links-Zeile, und „Balance lesen“ schickte jedes Nicht-Futures-Konto ohne MT5-Login in den Tradovate-Weg (konto_balance). Jetzt: app.py balance_lese_weg — Futures → konto_balance, CFD → mt5_balance (Login aus mt5_links, sonst die MT5-Nummer der External ID), CFD ohne Login → klare Meldung statt Tradovate; beide Wege (/admin/wd-plaene „balance“ und /admin/konto-balance-lesen). Im PC-Tab lehnt tvKontoBalanceJetzt CFD-Konten ab. Nichts mehr in den Prop-Firm-Einstellungen eintragen.
Status: erledigt

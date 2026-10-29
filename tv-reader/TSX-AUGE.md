# TopstepX-Auge einrichten (je PC mit Topstep-Konten)

Stand 27.10.2026. Das TopstepX-Auge ist ein Tampermonkey-Script im **TopstepX-Tab des Puls-Chrome**. Es liest Konto, offene Position und
den Flach-Beweis (dieselbe Lesung wie der Puls-Bot, `augen_tsx.js`) und meldet sie alle 0,1 s und bei jeder Änderung im Tab an das Panel
dieses PCs (seit 0.2.0, 29.10.2026 — vorher 0,25 s). Prophos schließt
damit den Fusion-Hedge eines Topstep-Trades (Big Trade mit Orbit-Hedge oder Winning Day), sobald die Position in TopstepX zu ist.
Rückfälle bleiben: Radar (Kurs über TP/SL + Puffer) und das Notfall-Level im Fusion-Terminal.

Voraussetzung: Puls-Chrome, Tampermonkey und „Nutzerscripts zulassen“ wie in `PULS-CHROME-USERSCRIPT.md` (Schritte C und D).
Das Panel muss mindestens den Stand mit der Route `/api/tsx-stand` haben (kommt mit dem nächsten Update von selbst).

## 1. Script installieren

**Seit 0.3.0 (29.10.2026) aktualisiert sich das Auge selbst:** Der Lader holt neue Fassungen vom Panel dieses PCs, und Prophos lädt
den TopstepX-Tab neu, wenn nichts läuft. Ein PC mit einem älteren Auge (0.2.0 und davor) bekommt die Lader-Fassung einmal von Puls
(Tampermonkey-Knopf „Aktualisieren“). Klappt das nicht, kommt eine ⚪-Meldung, dann einmal von Hand:

Im **Puls-Chrome** diese Adresse öffnen (das Panel liefert die Datei aus):

```
http://127.0.0.1:8770/userscript/tsx-auge.user.js
```

Tampermonkey zeigt „Installieren“ (neu) bzw. „Aktualisieren“ → drücken. Nur im Puls-Chrome, nicht im normalen Chrome.

## 2. TopstepX-Tab neu laden

Im Puls-Chrome auf den TopstepX-Tab gehen und **F5** drücken. Unten rechts die **Order-Karte** lassen (nicht das DOM), unten den
Reiter **Positions** offen lassen.

## 3. Kontrolle

```powershell
irm http://127.0.0.1:8770/api/tsx-stand
(irm http://127.0.0.1:8770/api/tsx-stand).stand.konto
```

Fertig, wenn `ok : True` und `alter_s` unter 1 kommt (auch mit dem Tab im Hintergrund). Die zweite Zeile zeigt das Konto: unter
`kontonr` steht die volle Kennung des Kontos, das TopstepX gerade zeigt (`abgekuerzt : False`). Die erste Zeile allein zeigt
`konto=` leer — PowerShell stellt verschachtelte Werte so dar, das ist kein Fehler. `stand.takt` sagt, wie das Script tickt:
`worker` (voller Takt) oder `interval` (TopstepX verbietet den Worker; dann hält der Puls-Chrome-Start ohne Hintergrund-Drosselung
den Takt, ab dem nächsten Neustart des Puls-Chrome). `stand.ausgeloggt : True` heißt: TopstepX ist ausgeloggt. Steht dort `ok : False` „kein TopstepX-Auge meldet“: Tab neu laden, sonst in Tampermonkey
prüfen, ob „Prophos TopstepX-Auge“ an ist.

## Was das Auge nie tut

- Es klickt nie und tippt nie. Es meldet nur.
- Geschlossen wird nur, wenn die Kennung exakt zum Plan-Konto passt, der Stand ≤ 1 s alt ist, die Position seit dem Hedge-Open schon
  einmal gesehen wurde und TopstepX „flach“ beweist („No Active Position“). Eine abgekürzte Kennung (`…`) zählt nicht. Dann schließen
  Radar oder Fusion-Level.
- Solange Puls auf diesem PC etwas tut (Order, Lesung, Rück-Login), zählt das Auge nicht. Danach beginnt die Konto-Ruhe neu.
- Ist TopstepX ausgeloggt (Login-Seite oder „session expired“), schließt das Auge nie. Läuft auf diesem PC ein Topstep-Trade mit Hedge,
  loggt Puls sich über den Rück-Login wieder ein (höchstens einmal je 10 min, Login-Klick nur mit gespeichertem Passwort). Bis dahin
  schließen Radar und Fusion-Level.

## Update von `augen_tsx.js`

Tampermonkey hält die per `@require` geladene `augen_tsx.js` im Cache. Ändert sich `augen_tsx.js`, im Script den Query-Teil von
`@require` (`?v=tsx-…`) und `@version` anheben. Tampermonkey holt die neue Fassung dann mit dem nächsten Script-Update von selbst.

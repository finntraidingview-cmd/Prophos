# Prophos lokal auf dem PC laufen lassen (Topstep-Verbindung aus der PC-IP)

**Das ist der einfachste Weg — ohne eine einzige Code-Änderung.** Frontend, „Topstep
verbinden", Trade-Plan, „Trade starten", Multiplier, Symbol-Mapping: alles bleibt exakt
wie heute. Es ändert sich nur, **wo** das Backend läuft — auf dem PC der Person statt auf
dem Railway-Server in Amsterdam. Damit kommen alle TopstepX-Verbindungen aus der IP
dieses PCs, dieselbe IP wie die manuelle Order.

## Warum das ohne Änderung funktioniert
In `prophos.html` steht schon heute:

    const TS_BACKEND = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? 'http://localhost:5000'
      : 'https://web-production-bec81.up.railway.app'

Rufst du Prophos also über `http://localhost:5000` auf, schickt das Frontend **automatisch
alle** Anfragen (TopstepX-Proxy, MetaApi, Mirror-Start/-Stop/-Status, Duplikum, News) an
das lokale Backend statt nach Amsterdam. `app.py` serviert `prophos.html` selbst — ein
Programm, ein Port, fertig.

Getestet: `app.py` startet standalone, `/` liefert das Frontend, `/version` und
`/mirror/status` antworten. Keine Pflicht-Umgebungsvariablen (DUP_EMAIL/DUP_PASSWORD sind
optional — ohne sie muss Duplikum wie gewohnt manuell verbunden werden).

## Einrichtung pro PC (einmal, ca. 10 Minuten)
1. **Python 3.10+** von python.org installieren — beim Setup **„Add python.exe to PATH"**
   ankreuzen.
2. Projekt auf den PC holen: den Ordner mit `app.py`, `prophos.html`, `requirements.txt`
   und `firm_rules.json` kopieren (oder `git clone` des Repos).
3. Eingabeaufforderung im Ordner öffnen (Adressleiste → `cmd` → Enter):

       pip install -r requirements.txt

4. **Starten:** `start-local-backend.bat` doppelklicken. Es öffnet sich ein Konsolenfenster
   (bei Absturz startet es sich nach 10 s selbst neu). Fenster **minimieren**, nicht
   schließen.
5. Im Browser auf diesem PC **`http://localhost:5000`** öffnen — nicht prophos.pages.dev.
   Am besten als Lesezeichen/Startseite setzen, damit nie versehentlich die Cloud-Version
   benutzt wird.
6. **Autostart** (damit du nie manuell starten musst): Windows-Aufgabenplanung →
   „Aufgabe erstellen…" → Trigger „Beim Start"/„Bei Anmeldung" → Aktion:
   `C:\<Pfad>\start-local-backend.bat` („Starten in" = derselbe Ordner) → Einstellungen:
   „Aufgabe neu starten, falls Fehler" alle 1 Minute, bis 99×; „Aufgabe beenden, falls
   länger ausgeführt als" **abwählen**.

## Beim ersten Mal auf localhost (wichtig, einmalig)
`http://localhost:5000` ist für den Browser eine **andere Herkunft** als
prophos.pages.dev. Alles, was im Browser-Speicher liegt, ist dort deshalb leer:
- **Topstep neu verbinden** (API-Key + Username eingeben) — genau der gewohnte Ablauf,
  nur einmal pro PC.
- Rechner-/Toggle-Einstellungen und scharfgeschaltete Mirror-Pläne beginnen leer.
- **Mirror-Pair neu einstellen** — die Pairs liegen in localStorage (`prophos_mirror_pairs`),
  also pro Herkunft getrennt. Auf localhost steht ein Pair mit STANDARDWERTEN:
  - Master-Account (TopstepX) auswählen — sonst „⚠ Accounts wählen", kein Start möglich.
  - **Multiplikator auf den gewohnten Wert setzen.** Die grüne Box rechts zeigt die
    resultierenden Lots — die MUSS mit dem bisherigen Wert übereinstimmen. Beispiel:
    0,1 → 1.0 Lots (richtig) vs. Default 0,8 → 8.0 Lots (achtfach zu großer Hedge!).
  - Häkchen **Echtzeit (BETA)** so setzen wie bisher (bei Finn: an) — sonst läuft eine
    andere Engine (Polling statt SignalR).
- **Nicht betroffen:** alles aus Supabase (Accounts, Trade-Pläne, Finanzen) — nach dem
  Login sofort wieder da.

## Zwei Regeln für den Betrieb
1. **Nie dasselbe Konto gleichzeitig lokal und über Railway scharfschalten.** Sonst
   spiegeln zwei Engines parallel → doppelte Hedge-Orders. Pro Person entweder lokal
   (empfohlen) oder Cloud, nicht beides.
2. **Updates: nichts zu tun.** `start-local-backend.bat` setzt `PROPHOS_FRONTEND` auf
   `https://prophos.pages.dev/prophos` — das Backend holt die Oberfläche bei jedem
   Seitenaufruf **live** von dort. Dein Update-Weg bleibt unverändert (GitHub →
   Cloudflare); die PCs haben danach automatisch die neue Version, ohne dass du auf
   einen einzigen PC musst. Die lokale `prophos.html` bleibt nur als Offline-Reserve
   liegen: ist pages.dev nicht erreichbar, wird automatisch sie ausgeliefert
   (Konsole zeigt dann „nutze lokale Datei"). Abschalten: die `set PROPHOS_FRONTEND`-Zeile
   in der .bat mit `REM` davor deaktivieren.

   Verifiziert am 29.07.2026: mit Variable = byte-identisch zur pages.dev-Version;
   ohne Variable = unverändertes Verhalten (lokale Datei); bei unerreichbarer URL =
   Fallback greift.

## Verhältnis zu `topstep-agent/`
Der separate Agent in `topstep-agent/` macht dasselbe Ziel auf einem anderen Weg (nur
Mirror, Steuerung über die Supabase-Tabelle `mirror_control`, ohne Browser). Er ist die
Reserve-Variante, falls das lokale Vollbackend mal nicht passt — z.B. wenn der Mirror
laufen soll, ohne dass jemand Prophos im Browser öffnet. Für den normalen Fall ist
**dieser** Weg hier der richtige, weil er das Frontend unverändert lässt.

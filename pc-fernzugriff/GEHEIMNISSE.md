# Geheimnisse auf den Windows-PCs — was liegt da, wer legt es an, was kann es

Stand 01.11.2026 (Live .1961, Slave 15). **Nur aus dem Code abgeleitet**, kein PC gelesen, keine Werte, keine Git-Historie.
Anlass: Claude soll per Tailscale + SSH auf die PCs. Vorher muss klar sein, was ein übernommener PC (oder ein neugieriger Kunde,
alle PCs stehen bei Kunden) damit gegen die Flotte, Supabase oder Finns Mac anfangen könnte. Werte stehen hier nie, nur Namen,
Herkunft und Rechte. Pfade: `C:\mt5-copier` (Copier/Panel/Bot/lokales Backend), `C:\tv-reader` bzw. `C:\Prophos\tv-reader` (Reader).

## 1. Übersicht

| # | Was | Wo auf dem PC | Wer legt es an | Was es kann |
|---|---|---|---|---|
| 1 | **PC-Schlüssel** `code_token.txt` | `C:\mt5-copier\code_token.txt` | Der eingeloggte Prophos-Tab holt ihn bei Railway und gibt ihn dem Panel (`prophos.html:79993`, `:80018` → `panel.py:5484-5500`) | Nur-Lese-Zugang zum Code über Railway, Rechte siehe §2. **Kein GitHub-Zugang, kein Push.** |
| 2 | **Feed-Schlüssel** `feed_token.txt` | Reader-Ordner (`reader-server.py:1903`) | Derselbe Tab, über `/feed-token` des Readers (`reader-server.py:950-956`) | Technisch derselbe Schlüssel wie #1 (`uid.pc.sig`): schreibt Kurse/Kerzen/Kontenliste dieser ID nach Supabase (§2). |
| 3 | **Supabase Anon-Key** | in der lokalen `prophos.html` (`prophos.html:14988-14989`) und `app.py:6204-6205` (Default fest im Code) | Repo, auf jedem PC per Selbst-Update | Öffentlicher Schlüssel; allein nur, was RLS für „anonym“ erlaubt. Gefährlich erst zusammen mit #4. |
| 4 | **Supabase-Login der ID** (Access-/Refresh-Token) | Standard-Chrome des Nutzers, localStorage von `prophos.pages.dev` (Prophos-Tab bleibt eingeloggt) | Der Kunde beim Login im Tab | Handelt als diese ID: alles, was die Seite kann, auch per direktem supabase-js ohne die Riegel der Oberfläche (S11-Befund `wd_konto_setzen`, `wd_tagesplan`: Policy `ALL` für `authenticated`). |
| 5 | **Supabase Service-Key** | **nicht auf dem PC.** Nur Railway-Env (`app.py:2757-2758`). Das lokale `app.py` startet ohne Env (`start-prophos.bat:13` setzt nur `PROPHOS_FRONTEND`) | — | — |
| 6 | **MT5-Logins** (Konto, Passwort, Server) | In MT5s eigener, verschlüsselter Kontodatenbank je Terminal (`KeepPrivate=1`, `provision.py:137-143`). `prophos-login.ini` nur transient, wird gelöscht (`panel.py:3733-3743`, `provision.py:1139`, `:1222`) | Panel beim Anlegen (Passwort kommt vom Tab per POST 127.0.0.1:8770, `panel.py:4617`) | MT5 verbindet sich beim Start selbst. Wer das Terminal bedienen kann, handelt auf dem Konto (Prop-Konten und das **Fusion-LIVE-Hedge-Konto**, Nummer steht in `config.vorlage.json:5`). |
| 7 | **Copier-Configs** `config*.json`, `status*.json`, `plans.json`, `pc_id.json` | `C:\mt5-copier` | Panel/Provisionierung (`panel.py:728`, `:1636`) | Keine Passwörter, aber Kontonummern, Pfade, Magic, Pläne. Identität des PCs (`pc_id` ist Teil von #1). |
| 8 | **TradingView/Tradovate-Sitzung** | Standard-Chrome (Reader-Tab) **und** Puls-Chrome `%LOCALAPPDATA%\Prophos\puls-chrome` (`order_bot.py:16567`, `:16581`) | Kunde bzw. Puls-Auto-Login (Benutzername aus der Config, Passwort nie aus Code: `order_bot.py:6396-6425`) | Eingeloggte Broker-Sitzung. Puls-Chrome lauscht mit **CDP auf 127.0.0.1:9333** (`order_bot.py:16565-16566`, `:16590`): jeder lokale Prozess kann die Broker-Sitzung fernsteuern. |
| 9 | **TopstepX-Passwort** | Chrome-Passwortspeicher des Puls-Chrome (Autofill, `order_bot.py:26102-26108`) | Kunde einmal von Hand | DPAPI-verschlüsselt, aber für denselben Windows-Benutzer entschlüsselbar. Handelt auf Topstep. |
| 10 | **TSX-/MetaApi-Token** `mirror-sessions.json` | `%USERPROFILE%\.prophos\mirror-sessions.json` (`app.py:1131-1141`, nur wenn das lokale Backend Spiegel-Paare fährt) | Lokales `app.py` | `tsxToken`, `maToken`, Konto-IDs: Zugang zu TopstepX-API und MetaApi, solange die Token gelten. `chmod 600` wirkt unter Windows nicht. |
| 11 | **Duplikum/MetaApi-Token im Browser** | Standard-Chrome, Prophos-Tab (gehen als Header `ma-token`, `dup-token` ans Backend, `app.py:401`, `:517`) | Kunde/Finn im Tab | Positionsdaten und Copier-Einstellungen bei Duplikum, MetaApi-Konto. `DUP_EMAIL/DUP_PASSWORD` liegen nur auf Railway (`app.py:279-280`). |
| 12 | **Tailscale-Knotenschlüssel + sshd** (neu, S11) | Tailscale-Dienst, `authorized_keys` mit Finns **öffentlichem** Schlüssel | S11 `setup-pc.ps1` | Der PC ist ein Knoten im Tailnet: erreicht andere Knoten, soweit die Tailscale-ACL es zulässt. Der private SSH-Schlüssel bleibt auf dem Mac. |
| 13 | **Parsec** | Parsec-Dienst | Finn | Bildschirm-Fernzugriff auf diesen PC; Konto-Login liegt beim Parsec-Client. |

Fehlerfoto-Upload (`app.py:17002`, Tor `_puls_fehlerbild_tor`) braucht **keinen** Schlüssel, nur eine bekannte `pc_id` + Deckel je Stunde.
Puls-Spur (`/puls-diagnose/<pc_id>`, `app.py:16900`, `order_bot.py:1042`) ebenso. Beides nur schreibend in Bilder/Spuren, nie Trades.

## 2. Der PC-Schlüssel genau (`code_token.txt`)

**Form:** `uid.pc.sig` — Prophos-User-ID, PC-Kennung, 40 Hex (`panel.py:203`, Muster `CODE_TOKEN_MUSTER`).
**Herkunft:** `POST /reader-feed-token` mit dem Supabase-Login des Tabs (`app.py:17286-17297`). Die Signatur ist ein HMAC über `uid|pc`,
Geheimnis aus dem **Service-Key abgeleitet** (`app.py:17182-17184`): kein eigenes Geheimnis, nicht widerrufbar außer über `CODE_SPERRE`
(Env, je User-ID, `app.py:17321`) oder Wechsel des Service-Keys (dann sind alle PC-Schlüssel ungültig).
**Wer liest ihn auf dem PC:** `panel.py:206`, `copier.py:121`, `order_bot.py:16878`, `polar_bot.py:69`, lokales `app.py:38074`, alle vier
Starter-Bats (`start-alles.bat:100`, `:198`; `start-copier.bat:24`; `start-panel.bat:31`; `start-prophos.bat:40`) und der Reader als
`feed_token.txt` (`start-reader.bat:27`, `start-verbinder.bat:22`).

**Was er auf Railway darf** (alle mit Header `X-Code-Token`, Prüfung `_code_zugang` `app.py:17317-17323`):

| Weg | Datei:Zeile | Recht |
|---|---|---|
| `GET /code/stand` | `app.py:17329` | lesen: Commit + VERSION |
| `GET /code/datei/<pfad>` | `app.py:19572`, Muster `:17306` | lesen: `app.py`, `prophos.html`, `sw.js`, `requirements.txt`, `mt5-copier/*`, `tv-reader/*` — **die ganze PC-Seite des Quellcodes**, mit jedem beliebigen PC-Schlüssel |
| `GET /code/tab-stand/<pc>` | `app.py:19702` | lesen: Tab-Stand und Riegel eines PCs |
| `POST /richtung/frei` | `app.py:17860` | lesen: ist Plan × Richtung frei (Antwort ja/nein) |
| `POST /pc/update-spur`, `/pc/tab-heil-spur` | `app.py:4663`, `:4693` | schreiben: ⚪-Alarm an die Master-IDs, 1× je Stunde je PC |
| `POST /reader-kurs` (als `X-Reader-Token`) | `app.py:19755-19778` | **schreiben: `tv_kurse`, `tv_kurs_1m`** für die ID im Schlüssel (Service-Role) |
| `POST` Kontenliste (als `X-Reader-Token`) | `app.py:19850-19858` | schreiben: `tv_konten` dieser ID × PC |

**Kann er ins GitHub-Repo pushen?** Nein. Auf dem PC gibt es keinen GitHub-Token und kein Git. Die „GitHub“-Rückfälle in den Bats und in
`app.py:665` holen ohne Schlüssel von `raw.githubusercontent.com`, was beim privaten Repo seit 07.10.2026 leer läuft. Railway liest das
Repo nur (Deploy). Der Schlüssel ist ein Lese-Ausweis für Railway und ein Schreib-Ausweis für Kursdaten, sonst nichts.

**Gültigkeit:** unbegrenzt, an User-ID + PC gebunden, nicht an die Maschine. Kopiert funktioniert er überall.

## 3. Was ein übernommener PC gegen Flotte, Supabase oder Mac tun könnte

Reihenfolge nach Schaden. „Übernommen“ heißt: jemand hat eine Shell als der Windows-Benutzer, unter dem der Stack läuft.

1. **Trades auf den Konten dieses PCs.** MT5-Terminals sind eingeloggt (#6), Puls-Chrome hat die Broker-Sitzung und hört auf CDP
   127.0.0.1:9333 (#8, `order_bot.py:16565`), TopstepX-Passwort im Autofill (#9). Das ist echtes Geld, inklusive Fusion-LIVE-Hedge.
   Braucht keinen Schlüssel aus dieser Liste, nur den Bildschirm oder CDP. Betrifft **nur die Konten dieses PCs**.
2. **Falsche Kurse für die ganze ID.** Mit `code_token.txt` als `X-Reader-Token` schreibt der PC `tv_kurse`/`tv_kurs_1m` (`app.py:19776-19778`).
   Der Hedge-Wächter schließt auf diesen Kursen (`app.py:17178`). Ein erfundener Kurs kann Hedges der **anderen PCs derselben ID** schließen
   oder festhalten. Railway prüft nur die Signatur, nicht die Plausibilität gegenüber anderen PCs (`reader_feed_zeilen` filtert Alter/Preis > 1000, `app.py:17205`).
3. **Als diese ID in Supabase handeln.** Supabase-Login im Standard-Chrome (#4) + Anon-Key (#3): direkte REST/RPC-Aufrufe an allen Riegeln
   der Oberfläche vorbei (S11-Notiz 01.11.2026: `wd_konto_setzen` ohne Besitzprüfung, `wd_farmer_regeln` Policy `ALL`). Reicht über diese ID
   hinaus, soweit Policies `authenticated` statt Besitzer prüfen. Beweis-Stelle: `prophos.html:16081` nennt den Capture-Riegel den einzigen.
4. **Quellcode abziehen.** `GET /code/datei/…` liefert `app.py`, `prophos.html`, Copier, Bot, Reader (`app.py:17306`, `:19572`). Genau das,
   wovor das private Repo schützen sollte (Finn 07.10.2026: „man kann Prophos ja jetzt klauen“). Jeder PC-Schlüssel reicht.
5. **Andere PCs im Tailnet erreichen** (#12). Jeder PC ist Tailscale-Knoten. Das lokale Backend lauscht auf **allen** Interfaces
   (`app.py:38332`, `host="0.0.0.0"`, Port 5000), also auch auf der Tailscale-Adresse. Panel (`panel.py:6551`) und Reader binden 127.0.0.1,
   die sind von außen zu. Mit sshd auf allen PCs und Finns öffentlichem Schlüssel kommt ein übernommener PC **nicht** auf die anderen
   (der private Schlüssel liegt nur auf dem Mac), außer die ACL lässt PC→PC-Verkehr zu und ein Dienst dort ist offen (5000!).
6. **Finns Mac.** Nichts auf dem PC authentifiziert gegen den Mac: kein Mac-Schlüssel, kein Token. Risiko nur, wenn der Mac im Tailnet
   Dienste freigibt (Flask `localhost:5000` als launchd-Job, laut Memory nur localhost) oder SSH auf dem Mac für Tailnet-Knoten offen ist.
   Das ist Sache der Tailscale-ACL (S11/S14), nicht einer Datei auf dem PC.
7. **Alarme vergiften / zumüllen.** `/pc/update-spur`, `/pc/tab-heil-spur` (⚪ an Master-IDs, 1×/h je PC), Fehlerfotos und Puls-Spur ohne
   Schlüssel mit fremder `pc_id` (`app.py:17002`, `:16900`). Lästig, kein Geld.
8. **TSX-/MetaApi-Token** aus `mirror-sessions.json` (#10), nur auf PCs, deren lokales Backend Spiegel-Paare fährt: API-Zugang zum
   Topstep-/MetaApi-Konto, bis der Token abläuft.

## 4. Was daraus folgt (nur Befund, nichts gebaut)

- Der PC-Schlüssel ist bewusst „kein neues Geheimnis“ (`app.py:17304`), aber er trägt **zwei** Rollen: Code lesen und Kurse schreiben. Für
  Punkt 2 und 4 wäre eine Trennung oder ein PC-gebundener Anteil (z. B. Hash der Tailscale-Knoten-ID) der Hebel. Sperren geht heute nur
  je User-ID (`CODE_SPERRE`), nicht je PC.
- `app.py:38332` `host="0.0.0.0"` am lokalen Backend ist seit Tailscale ein offener Port im Tailnet. Vor dem Rollout von S11 prüfen, ob die
  ACL PC→PC auf 5000 zulässt; sonst `127.0.0.1` binden, wenn `PROPHOS_FRONTEND` gesetzt ist.
- Nichts auf dem PC gibt Zugang zum Mac, zu GitHub oder zum Service-Key. Der größte Hebel bleibt der Bildschirm selbst (Punkt 1).
- `diagnose.ps1` daneben listet alle Dateien aus §1 nur mit Größe/Datum und maskiert Schlüssel-Muster in jeder Ausgabezeile.

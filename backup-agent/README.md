# Backup-Agent

Tägliches Voll-Backup aller Supabase-Tabellen auf Finns Mac — die Versicherung,
falls Supabase down ist oder Daten verloren gehen. Eingerichtet 01.09.2026.

## Was passiert

Jeden Tag um **06:30** (und beim Hochfahren, falls der Mac um 06:30 aus war)
zieht `backup.py` **alle Tabellen** aus dem Supabase-Projekt `gxhkannmzpyuepxlepta`
und legt einen kompletten Tages-Schnappschuss ab:

```
~/Prophos-Backups/2026-09-01/
├── accounts.csv                     ← eine CSV pro Tabelle (für Wiederherstellung)
├── trade_plans.csv
├── …
├── Prophos-Backup_2026-09-01.xlsx   ← alles in EINER Excel-Mappe (für Google
│                                      Sheets: auf sheets.google.com reinziehen)
├── _ANSEHEN.html                    ← alle Tabellen im Browser (der Mac hat kein
│                                      Tabellenprogramm — das hier öffnet überall)
└── _INFO.txt                        ← Zeilenzahlen + etwaige Fehler
```

- **30 Tage Aufbewahrung**, ältere Tagesordner werden automatisch gelöscht.
  Das ist zugleich eine Zeitmaschine: versehentlich Gelöschtes steht im
  Schnappschuss von gestern.
- Danach Spiegel-Versuch nach **iCloud Drive/Prophos-Backups** (überlebt einen
  Mac-Ausfall). macOS verweigert launchd-Jobs den iCloud-Zugriff, solange
  `python3` keinen Festplattenvollzugriff hat (Systemeinstellungen →
  Datenschutz & Sicherheit → Festplattenvollzugriff → `/usr/bin/python3`
  hinzufügen). Ohne das ist das Backup trotzdem vollständig — nur eben lokal.
- Log: `~/Library/Logs/prophos-backup.log`

## Zugang (bewusst minimal)

Das Backup nutzt die **Nur-Lese-Rolle `backup_reader`**
(`sql/2026-09-01_backup-reader.sql`) — kein service_role-Key auf dem Mac.
Selbst wenn die Zugangsdaten abhandenkommen, kann damit nichts verändert werden.

- Zugangsdaten: `~/.prophos/backup-config.json` (chmod 600, NIE im Repo)
- TLS voll verifiziert gegen die gepinnte Supabase-Root-CA
  (`~/.prophos/supabase-ca.crt`, „Supabase Root 2021 CA")
- Verbindung über den Supavisor-Pooler (`aws-0-eu-west-1`), weil der direkte
  DB-Host nur per IPv6 erreichbar ist

## Neue Tabelle angelegt und das Backup meldet „permission denied"?

Gewollt: neue Tabellen sollen laut scheitern statt still leer gesichert zu
werden. Abhilfe: `sql/2026-09-01_backup-reader.sql` erneut einspielen
(idempotent, holt alle neuen Tabellen nach).

## Manuell ausführen / Job verwalten

```bash
python3 /Applications/Prophos/backup-agent/backup.py
```

```bash
launchctl kickstart -k gui/501/com.prophos.backup
```

Der aktive launchd-Job liegt unter `~/Library/LaunchAgents/com.prophos.backup.plist`;
die Datei hier im Ordner ist die Repo-Kopie. Nach Änderungen: neu kopieren, dann
`launchctl bootout gui/501/com.prophos.backup` und wieder `bootstrap`.

# Userscript 0.10.9 nur für das Testgerät (Schluss einfach, Finn 02.11.2026)

`tv-reader-0.10.9.user.js` ist die Fassung mit der einfachen Schließ-Regel. Sie liegt bewusst nicht unter `tv-reader/`: Reader, kern.json, /code und der Tampermonkey-Rollout lesen nur `tv-reader/tv-reader.user.js` (0.10.7). Die neue Regel im Tab greift erst, wenn der Positions-Tab 0.10.9 meldet.

Aufs Testgerät, von Hand im Puls-Chrome: Tampermonkey-Dashboard → „Prophos TV-Reader“ öffnen, Inhalt der Datei einfügen, speichern, TradingView-Tab neu laden. Kein Rückdrehen: Tampermonkey aktualisiert nur auf eine höhere Version, der Lader startet keine ältere, tv-tm-update und die Versions-Wache greifen nur bei einer älteren Fassung.

Zurück: dieselben Schritte mit `tv-reader/tv-reader.user.js`, wegen der niedrigeren Version als Inhalt einfügen.

Nach Finns Test (eigener Commit): Datei nach `tv-reader/tv-reader.user.js` kopieren, `TVTM_VERSION_SOLL` in prophos.html auf 0.10.9, diesen Ordner löschen, Pfad in `tools/selftest_reader_schluss.py` zurück auf `tv-reader/`.

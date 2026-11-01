# -*- coding: utf-8 -*-
"""auftrag.py — wird vom Mac per SSH aufgerufen (do.sh), EIN Aufruf: Auftrag ablegen, auf das Ergebnis warten, JSON ausgeben.
02.11.2026, Auftrag PC-AGENT. Warum: eine Rundreise = eine SSH-Verbindung (ControlMaster) statt scp + ssh-Polling; Python startet
in ~50 ms, PowerShell braucht ~1 s. Aufruf:  python auftrag.py <base64-JSON> [wartezeit_s]
Schreibt …\\auftraege\\<id>.json (erst .tmp, dann umbenannt), wartet auf …\\ergebnisse\\<id>.json (Polling 50 ms, Standard 20 s)
und druckt dessen Inhalt als einzige stdout-Zeile. Exit 0 = Ergebnis da (ok oder Fehler steht im JSON), 2 = Aufruf, 3 = kein
Ergebnis in der Zeit (Agent läuft nicht? — agent-aufgabe.ps1), 4 = Auftrag kaputt. Nichts Weiteres: Fotos holt do.sh per scp.
"""
import base64
import json
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
AUFTRAEGE = os.path.join(WURZEL, "auftraege")
ERGEBNISSE = os.path.join(WURZEL, "ergebnisse")


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("Aufruf: auftrag.py <base64-JSON> [wartezeit_s]\n")
        return 2
    try:
        auftrag = json.loads(base64.b64decode(argv[1]).decode("utf-8"))
        if not isinstance(auftrag, dict) or not isinstance(auftrag.get("aktionen"), list):
            raise ValueError("JSON-Objekt mit Liste 'aktionen' erwartet")
    except Exception as ex:
        sys.stderr.write("Auftrag kaputt: %s\n" % ex)
        return 4
    warte = float(argv[2]) if len(argv) > 2 else 20.0
    aid = str(auftrag.get("id") or "").strip()
    if not aid or not all(c.isalnum() or c in "-_" for c in aid):
        aid = time.strftime("%Y%m%d-%H%M%S") + "-%06x" % (int.from_bytes(os.urandom(3), "big"))
        auftrag["id"] = aid
    os.makedirs(AUFTRAEGE, exist_ok=True)
    os.makedirs(ERGEBNISSE, exist_ok=True)
    ziel = os.path.join(ERGEBNISSE, aid + ".json")
    if os.path.exists(ziel):
        os.remove(ziel)
    tmp = os.path.join(AUFTRAEGE, aid + ".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(auftrag, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(AUFTRAEGE, aid + ".json"))
    ende = time.time() + warte
    while time.time() < ende:
        if os.path.exists(ziel):
            try:
                with open(ziel, "r", encoding="utf-8") as f:
                    erg = json.load(f)
                # ASCII-sicher (\uXXXX): stdout in der ssh-Pipe ist auf Windows cp1252, Umlaute in Fenstertiteln würden sonst abstürzen
                sys.stdout.write(json.dumps(erg, ensure_ascii=True) + "\n")
                return 0
            except ValueError:
                time.sleep(0.05)
                continue
        time.sleep(0.05)
    agent_da = os.path.exists(os.path.join(AUFTRAEGE, aid + ".json.lauf"))
    sys.stderr.write("Kein Ergebnis nach %.0f s (%s)\n" % (warte, "Auftrag läuft noch" if agent_da else
                                                           "Auftrag nie beansprucht — läuft die Aufgabe „Prophos Agent“? agent-aufgabe.ps1"))
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))

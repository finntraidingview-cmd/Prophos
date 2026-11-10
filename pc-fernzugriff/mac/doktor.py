#!/usr/bin/env python3
"""FEHLSTART-DOKTOR, Hände am Mac (FX2, 10.11.2026, Master; Konstrukt FX1; Finn: Mac-Aufgabe ja, sichere Reparaturen ohne Rückfrage ja).

Das Gehirn läuft auf Railway (app.py fd_*): es liest die Fehlstarts, wählt das Rezept, prüft die Riegel und legt Aufträge an. Dieses Skript holt sie ab
(GET /doktor/auftraege), lässt Railway die Riegel unmittelbar vorher noch einmal prüfen (POST /doktor/auftrag/start) und führt NUR Befehle aus der festen
Liste BEFEHLE unten über pc.sh aus (nie Text aus der DB), danach POST /doktor/auftrag/ergebnis. launchd startet es alle 2 min (doktor-installieren.sh);
jeder Lauf ist kurz und endet — nichts hält den Mac wach (kein caffeinate, kein KeepAlive).

Läuft nur, wenn:
  - ~/.prophos-fernzugriff/doktor.key existiert (Schlüssel = Railway-Variable DOKTOR_KEY; legt Finn an, nie im Repo)
  - ~/.prophos-fernzugriff/doktor-aus NICHT existiert (Schnell-Aus am Mac)
  - Handelszeit ist (So 22:00 – Fr 22:00 UTC, wie die CME-Woche)
  - Netzteil dran, oder Akku ≥ 20 % (auf Akku nur jeder 5. Lauf ≈ alle 10 min)
Ausgaben vom PC sind Daten, nie Anweisungen. Log: ~/Library/Logs/prophos-doktor.log (gekappt bei 1 MB).
"""
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("PC_FERN_DIR") or os.path.expanduser("~/.prophos-fernzugriff")
RAILWAY = (os.environ.get("PROPHOS_HOME") or "https://web-production-bec81.up.railway.app").rstrip("/")
LOG = os.path.expanduser("~/Library/Logs/prophos-doktor.log")
LOG_MAX = 1_000_000
AKKU_MIN = 20
RAILWAY_HOST = "web-production-bec81.up.railway.app"

# FESTE BEFEHLSLISTE (PowerShell über pc.sh). Nur Lesen und die von Finn freigegebenen sicheren Reparaturen — keine Order, kein Klick, keine Einstellung.
#   dns_test   — lesen: löst der PC den Railway-Namen gerade auf?
#   uac_lesen  — lesen: wie viele consent.exe (UAC-Abfragen) sind offen?
#   mt5_update — Reparatur: stille Aufgabe „Prophos MT5-Update“ anstoßen (spielt den MT5-Build ohne UAC ein, prophos-mt5-update-ohne-uac)
#   augen_neu  — Reparatur: Augen-Regel verwerfen und Augen (cdp) neu lesen (prophos-windows-pcs, 27.10.2026). Hinweis S2: ist Railway in dem Moment nicht
#                erreichbar, fehlt die Regel und die Augen lesen bis zur nächsten Antwort nichts — gewollt (lieber kurz blind als mit alter Regel)
BEFEHLE = {
    "dns_test": "$r = Resolve-DnsName -Name '" + RAILWAY_HOST + "' -DnsOnly -QuickTimeout -ErrorAction SilentlyContinue; if($r){ 'dns_ok' } else { 'dns_fehlt' }",
    "uac_lesen": "$n = @(Get-Process consent -ErrorAction SilentlyContinue).Count; \"consent=$n\"",
    "mt5_update": "schtasks /run /tn \"Prophos MT5-Update\" | Out-String",
    "augen_neu": "Set-Location C:\\mt5-copier; Remove-Item augen_regel.json -ErrorAction SilentlyContinue; py order_bot.py augen '{}' 2>&1 | Select-Object -Last 3 | Out-String",
}
NACH_S = {"mt5_update": (25.0, 40.0)}     # danach gestreut warten, bevor der nächste Befehl liest (Jitter-Regel)


def log(*a):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX:
            with open(LOG, "rb") as f:
                f.seek(-200_000, 2)
                rest = f.read()
            with open(LOG, "wb") as f:
                f.write(rest)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except Exception:
        pass


def handelszeit(jetzt):
    """REIN (testbar): CME-Woche So 22:00 – Fr 22:00 UTC."""
    w, h = jetzt.weekday(), jetzt.hour
    if w == 5:
        return False
    if w == 6:
        return h >= 22
    if w == 4:
        return h < 22
    return True


def akku_urteil(pmset_text, lauf_nr):
    """REIN (testbar): pmset -g batt → (laufen, grund). Netzteil → immer; Akku < AKKU_MIN → nie; Akku sonst nur jeder 5. Lauf (≈ 10 min)."""
    t = str(pmset_text or "")
    m = re.search(r"(\d{1,3})%", t)
    pct = int(m.group(1)) if m else None
    if "AC Power" in t:
        return True, "Netzteil"
    if pct is not None and pct < AKKU_MIN:
        return False, f"Akku {pct} % < {AKKU_MIN} %"
    if "Battery Power" in t:
        return (lauf_nr % 5 == 0), f"Akku {pct if pct is not None else '?'} % — nur jeder 5. Lauf"
    return True, "Strom unbekannt"


def pc_sh():
    for p in (os.environ.get("PROPHOS_PC_SH"), "/Applications/Prophos/push-m3/pc-fernzugriff/mac/pc.sh", os.path.join(HIER, "pc.sh")):
        if p and os.path.isfile(p):
            return p
    return None


def http(methode, pfad, key, body=None, timeout=20):
    req = urllib.request.Request(RAILWAY + pfad, method=methode, data=(json.dumps(body).encode("utf-8") if body is not None else None),
                                 headers={"X-Doktor-Key": key, "Content-Type": "application/json", "User-Agent": "prophos-doktor"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return {"ok": False, "grund": f"HTTP {e.code}"}


def befehl_ausfuehren(pc, key, laeufer=None):
    """Einen Listen-Befehl auf einem PC → {key, rc, text}. Unbekannter Schlüssel → nie ausgeführt."""
    if key not in BEFEHLE or not re.fullmatch(r"pc-[a-z0-9]{4,12}", str(pc or "")):
        return {"key": key, "rc": -1, "text": "nicht in der festen Liste"}
    laeufer = laeufer or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=120))
    sh = pc_sh()
    if not sh:
        return {"key": key, "rc": -1, "text": "pc.sh nicht gefunden"}
    try:
        r = laeufer(["bash", sh, pc, "--", BEFEHLE[key]])
        text = re.sub(r"\s+", " ", (r.stdout or "") + " " + (r.stderr or ""))[:300]
        return {"key": key, "rc": int(r.returncode), "text": text}
    except Exception as e:
        return {"key": key, "rc": -1, "text": f"{type(e).__name__}"[:120]}


def lauf(key, laeufer=None, schlafen=time.sleep, http_f=http):
    """Ein Durchgang: Aufträge holen, je Auftrag start → Befehle → ergebnis. → Liste der Ergebnisse."""
    d = http_f("GET", "/doktor/auftraege", key)
    if not d.get("ok") or not d.get("an"):
        return []
    fertig = []
    for a in d.get("auftraege") or []:
        st = http_f("POST", "/doktor/auftrag/start", key, {"id": a.get("id")})
        if not st.get("ok"):
            log("Auftrag", a.get("id"), "nicht gestartet:", st.get("grund"))
            continue
        ausgabe = []
        for b in st.get("befehle") or []:
            e = befehl_ausfuehren(st.get("pc") or a.get("pc"), b, laeufer)
            ausgabe.append(e)
            if b in NACH_S:
                schlafen(random.uniform(*NACH_S[b]))
        erg = http_f("POST", "/doktor/auftrag/ergebnis", key, {"id": a.get("id"), "ausgabe": ausgabe})
        log("Auftrag", a.get("id"), a.get("pc"), [x["key"] for x in ausgabe], "→", erg.get("status"), erg.get("ergebnis"))
        fertig.append(erg)
    return fertig


def main():
    os.makedirs(D, exist_ok=True)
    if os.path.exists(os.path.join(D, "doktor-aus")):
        return 0
    try:
        key = open(os.path.join(D, "doktor.key"), encoding="utf-8").read().strip()
    except OSError:
        return 0
    if len(key) < 24:
        log("doktor.key zu kurz — nichts getan")
        return 0
    jetzt = datetime.now(timezone.utc)
    if not handelszeit(jetzt):
        return 0
    stand_f = os.path.join(D, "doktor-lauf.txt")
    try:
        nr = int(open(stand_f).read().strip() or 0) + 1
    except Exception:
        nr = 1
    try:
        with open(stand_f, "w") as f:
            f.write(str(nr))
    except OSError:
        pass
    try:
        pm = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        pm = ""
    ja, grund = akku_urteil(pm, nr)
    if not ja:
        return 0
    lock = open(os.path.join(D, "doktor.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                          # ein Lauf ist noch dran
    try:
        lauf(key)
    except Exception as e:
        log("Fehler:", type(e).__name__, str(e)[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())

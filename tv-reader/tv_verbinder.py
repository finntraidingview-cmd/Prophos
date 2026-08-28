#!/usr/bin/env python3
"""Prophos TV-Verbinder — Orbit (bis 28.08.2026 "Echo +"): Reader-Stand -> PROPHOS1-Snapshot fuer copier.py.

Das fehlende Kettenglied des einfachen Spiegel-Wegs (28.08.2026, Finns Ansage:
"TradingView-Order vom Windows-PC lesen + auf das Windows-MT5-Terminal
spiegeln"): liest alle 0,5 s den Stand des lokalen reader-servers
(http://127.0.0.1:8790/positions) und schreibt daraus per tv_snapshot.py das
PROPHOS1-CSV, das mt5-copier/copier.py ohnehin liest. Der Copier braucht NULL
Aenderungen — der TV-Reader ist fuer ihn einfach ein weiterer Master (eigene
Instanz-Config, siehe mt5-copier/config.tvplus.vorlage.json).

Frische-Doktrin (stale != flat, die Versicherung gegen "Hedge blind auf alten
Daten"):
  · Reader pausiert (an=false)  -> es wird NICHT geschrieben
  · Reader-Daten aelter 10 s    -> es wird NICHT geschrieben
  · reader-server nicht erreichbar -> es wird NICHT geschrieben
  In allen drei Faellen friert das CSV ein (seq bleibt stehen) — der Copier
  meldet nach 15 s "Snapshot unveraendert" und laesst die Hedges STEHEN.
  Ein pausierter/toter Reader schliesst also nie einen Hedge.

SL/TP werden bewusst GENULLT (sltp_uebernehmen=false, Default): TradingView
liefert FUTURES-Preise (NQ ~29.600), der Fusion-Hedge laeuft auf dem CFD
NAS100 mit anderer absoluter Preisskala (Basis/Contango-Abstand). Die
Notfall-Level des Copiers (plan_sltp) wuerden aus Futures-Leveln also FALSCHE
Hedge-Level rechnen — bis die Preisskala-Umrechnung gebaut ist, gilt
"leer statt falsch". 0.0 im Snapshot heisst fuer den Copier ehrlich
"Master hat kein Level".

Nur Python-Standardbibliothek. `python3 tv_verbinder.py --selftest` prueft die
Gates und das CSV-Format ohne Netz und ohne MT5 (laeuft auch auf dem Mac).
"""
import json
import os
import sys
import time
import urllib.request

import tv_snapshot

HIER = os.path.dirname(os.path.abspath(__file__))
CONFIG_DATEI = os.path.join(HIER, "verbinder.config.json")

DEFAULTS = {
    "reader_url": "http://127.0.0.1:8790/positions",
    "server_label": "TV:tradovate",
    "snapshot_file": "prophos_tv.csv",
    "common_files_dir": "",          # leer = Windows-Standard (wie copier.py)
    "intervall_s": 0.5,
    "max_datenalter_s": 10,
    "sltp_uebernehmen": False,
}


def lade_config():
    try:
        with open(CONFIG_DATEI, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        sys.exit(f"verbinder.config.json fehlt ({CONFIG_DATEI}) — "
                 f"verbinder.config.example.json kopieren und ausfuellen.")
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"verbinder.config.json nicht lesbar: {e}")
    out = dict(DEFAULTS)
    out.update({k: v for k, v in cfg.items() if not k.startswith("_")})
    if not int(out.get("master_login") or 0):
        sys.exit("master_login fehlt in verbinder.config.json — muss dem "
                 "master_expected_login der Copier-Config (config-tvplus.json) entsprechen.")
    return out


def common_dir(cfg):
    """DIESELBE Aufloesung wie copier.py (Zeile ~743) — beide MUESSEN auf
    denselben Ordner zeigen, sonst schreibt der Verbinder ins Leere."""
    return cfg.get("common_files_dir") or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")


def hole_stand(url, timeout=2.0):
    """Reader-Stand holen. None = nicht erreichbar/kaputt (Gate: nicht schreiben)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def pruefe_stand(stand, *, max_alter_s, jetzt_ms=None):
    """REIN RECHNEND (Selftest): entscheidet, ob aus diesem Stand geschrieben
    werden darf. Rueckgabe (ok, grund) — grund ist der Anzeige-Zustand."""
    if stand is None:
        return False, "reader offline"
    if stand.get("an") is False:
        return False, "pausiert"
    ts = stand.get("ts") or 0
    jetzt = jetzt_ms if jetzt_ms is not None else time.time() * 1000
    if not ts or jetzt - float(ts) > max_alter_s * 1000:
        return False, f"Daten zu alt (> {max_alter_s}s)"
    return True, "liest live"


def positionen_fuer_snapshot(stand, *, sltp_uebernehmen):
    """Positionsliste fuer baue_snapshot vorbereiten. SL/TP-Nullung siehe
    Modul-Docstring (Futures- vs. CFD-Preisskala — leer statt falsch)."""
    pos = list(stand.get("positionen") or [])
    if sltp_uebernehmen:
        return pos
    return [dict(p, sl=None, tp=None) for p in pos]


def schreibe_atomar(pfad, text):
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="ascii", errors="replace") as f:
        f.write(text)
    os.replace(tmp, pfad)


def main():
    cfg = lade_config()
    ordner = common_dir(cfg)
    ziel = os.path.join(ordner, str(cfg["snapshot_file"]))
    if not os.path.isdir(ordner):
        sys.exit(f"Zielordner existiert nicht: {ordner} — common_files_dir in "
                 f"verbinder.config.json pruefen (muss der Ordner sein, aus dem "
                 f"copier.py die Snapshots liest).")

    print("=" * 72)
    print(" Orbit · TV-Verbinder · Reader -> PROPHOS1-Snapshot")
    print(f"   Reader   {cfg['reader_url']}")
    print(f"   Ziel     {ziel}")
    print(f"   Master   {cfg['master_login']} @ {cfg['server_label']}")
    print(f"   SL/TP    {'werden uebernommen (ACHTUNG Preisskala!)' if cfg['sltp_uebernehmen'] else 'genullt (leer statt falsch)'}")
    print("=" * 72)

    seq = 0
    zustand = None       # letzter Anzeige-Zustand — Wechsel kommen als eigene Zeile
    while True:
        stand = hole_stand(cfg["reader_url"])
        ok, grund = pruefe_stand(stand, max_alter_s=float(cfg["max_datenalter_s"]))
        if grund != zustand:
            zeit = time.strftime("%H:%M:%S")
            print(f"\n[{zeit}] Zustand: {grund}"
                  + ("" if ok else " — CSV friert ein, Copier haelt die Hedges"))
            zustand = grund
        if ok:
            seq += 1
            pos = positionen_fuer_snapshot(stand, sltp_uebernehmen=bool(cfg["sltp_uebernehmen"]))
            csv, skips = tv_snapshot.baue_snapshot(
                pos, login=int(cfg["master_login"]), server=str(cfg["server_label"]),
                seq=seq, unixtime=int(time.time()))
            try:
                schreibe_atomar(ziel, csv)
            except OSError as e:
                print(f"\n[WARN] Snapshot nicht schreibbar: {e}")
            n = csv.count("\nP;")
            uebersprungen = f" · {len(skips)} uebersprungen" if skips else ""
            print(f"\r[{time.strftime('%H:%M:%S')}] seq {seq} · {n} Pos{uebersprungen}"
                  .ljust(100)[:100], end="", flush=True)
        time.sleep(float(cfg["intervall_s"]))


# ------------------------------------------------------------------ Selbsttest
def _selftest():
    n = 0

    def ok(cond, name):
        nonlocal n
        assert cond, f"FEHLGESCHLAGEN: {name}"
        n += 1

    jetzt = 1787900000000.0

    # Gates: genau die drei Nicht-schreiben-Faelle + der Gut-Fall
    ok(pruefe_stand(None, max_alter_s=10, jetzt_ms=jetzt) == (False, "reader offline"),
       "offline -> nicht schreiben")
    ok(pruefe_stand({"an": False, "ts": jetzt, "positionen": []},
                    max_alter_s=10, jetzt_ms=jetzt)[0] is False, "pausiert -> nicht schreiben")
    ok(pruefe_stand({"an": True, "ts": jetzt - 11000, "positionen": []},
                    max_alter_s=10, jetzt_ms=jetzt)[0] is False, "11s alt -> nicht schreiben")
    ok(pruefe_stand({"an": True, "ts": 0, "positionen": []},
                    max_alter_s=10, jetzt_ms=jetzt)[0] is False, "ts fehlt -> nicht schreiben")
    ok(pruefe_stand({"an": True, "ts": jetzt - 3000, "positionen": []},
                    max_alter_s=10, jetzt_ms=jetzt) == (True, "liest live"), "frisch -> schreiben")
    # altes reader-server-Format ohne 'an' (v0.1): kein an-Feld heisst AN
    ok(pruefe_stand({"ts": jetzt, "positionen": []},
                    max_alter_s=10, jetzt_ms=jetzt)[0] is True, "ohne an-Feld -> an")

    # SL/TP-Nullung (Preisskala-Riegel)
    stand = {"an": True, "ts": jetzt, "positionen": [
        {"symbol": "CME_MINI:NQ1!", "seite": "Long", "menge": "2",
         "einstieg": "29.618,25", "sl": "29.550,00", "tp": "29.720,00", "pnl": "+190,00 USD"}]}
    pos0 = positionen_fuer_snapshot(stand, sltp_uebernehmen=False)
    ok(pos0[0]["sl"] is None and pos0[0]["tp"] is None, "SL/TP genullt (Default)")
    ok(stand["positionen"][0]["sl"] == "29.550,00", "Original-Stand unveraendert")
    pos1 = positionen_fuer_snapshot(stand, sltp_uebernehmen=True)
    ok(pos1[0]["sl"] == "29.550,00", "sltp_uebernehmen=true reicht durch")

    # CSV aus genullten Positionen: SL/TP im Snapshot = 0.0 ('kein Level')
    csv, _ = tv_snapshot.baue_snapshot(pos0, login=12345, server="TV:tradovate",
                                       seq=7, unixtime=1787900000)
    zeile = [l for l in csv.splitlines() if l.startswith("P;")][0]
    ok(zeile.endswith(";0.00000000;0.00000000"), "CSV traegt SL/TP 0.0")

    # Gegen den echten Copier-Parser, wenn erreichbar (wie tv_snapshot-Selftest)
    try:
        sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
        import copier
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(csv); pfad = f.name
        snap = copier.read_snapshot(pfad, expect_login=12345)
        os.unlink(pfad)
        ok(snap is not None and snap["seq"] == 7, "copier.read_snapshot liest das CSV")
        p = snap["positions"][0]
        ok(p["sl"] == 0.0 and p["tp"] == 0.0 and p["price_open"] == 29618.25,
           "Copier: SL/TP 0.0, Entry echt")
        # plan_sltp mit 0.0-Leveln: loescht Level statt falsche zu setzen
        ziel = copier.plan_sltp(p, faktor=110, min_puffer_punkte=100, point=0.01, digits=2)
        ok(ziel == {"tp": 0.0, "sl": 0.0}, "plan_sltp: 0.0-Level -> Level loeschen, nie erfinden")
        print(f"tv_verbinder Selbsttest: {n} Checks bestanden (inkl. echtem copier.py)")
        return
    except ImportError:
        pass
    print(f"tv_verbinder Selbsttest: {n} Checks bestanden (copier.py nicht geladen)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\nbeendet.")

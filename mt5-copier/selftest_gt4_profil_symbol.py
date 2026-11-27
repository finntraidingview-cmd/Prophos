#!/usr/bin/env python3
"""Selbsttest GT4 (27.11.2026, Goat Funded Trader): Chart-Symbol der Profil-Injektion.
Befund pc-2zc2we (…3686/…3687/…3752): _inject_ea_into_profile hängte das Lese-EA ans erste Chart des Profils („EURUSD“). GFT kennt nur „EURUSD.x“ →
Journal „ProphosHedgeReader (EURUSD,H1) … failed (symbol synchronization timeout)“, EA entfernt, nie ein Snapshot. GT3 stellte nur [StartUp] um.
Prüft: _chr_symbol_passend (rein) und _inject_ea_into_profile gegen ein Wegwerf-Profil (UTF-16 mit BOM wie MT5, dazu UTF-8): neue Injektion und
bereits injiziertes Profil bekommen bei GFT „EURUSD.x“; ohne startup_symbol bleibt jede Datei wie vor GT4 (Chart-Symbol unverändert).
Ohne Windows/Netz. Aufruf: python3 mt5-copier/selftest_gt4_profil_symbol.py"""
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import provision  # noqa: E402
import panel  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


CHR = "<chart>\r\nid=1\r\nsymbol=%s\r\ndescription=Euro vs US Dollar\r\nperiod_type=1\r\nperiod_size=1\r\n</chart>\r\n"
EA = "<expert>\r\nname=ProphosHedgeReader\r\npath=Experts\\ProphosHedgeReader.ex5\r\n</expert>\r\n"

print("1) _chr_symbol_passend (rein)")
P = panel._chr_symbol_passend
t, g = P(CHR % "EURUSD", "EURUSD.x")
check(g and "symbol=EURUSD.x\r\n" in t and t.count("symbol=") == 1 and "description=Euro vs US Dollar" in t, "GFT: EURUSD → EURUSD.x, Rest unverändert")
t, g = P(CHR % "USDJPY", "EURUSD.x")
check(g and "symbol=EURUSD.x\r\n" in t, "GFT: anderes Symbol ohne Endung (USDJPY) → EURUSD.x")
for s in ("EURUSD.x", "NAS100.x"):
    t, g = P(CHR % s, "EURUSD.x")
    check(not g and t == CHR % s, f"GFT: Chart schon mit Endung ({s}) → bitgleich")
for sym in ("EURUSD", "", None, "a\nb"):
    t, g = P(CHR % "EURUSD", sym)
    check(not g and t == CHR % "EURUSD", f"Start-Symbol ohne Endung ({sym!r}) → bitgleich")
for sym in ("US100.cash", "NAS100.x", "US_TECH100", "USTEC#"):   # Prüfer GT4: Firmen-Symbol als Start-Symbol belegt keine Endung für EURUSD
    t, g = P(CHR % "EURUSD", sym)
    check(not g and t == CHR % "EURUSD", f"Start-Symbol ist kein EURUSD<Endung> ({sym}) → laufendes EURUSD-Chart bleibt bitgleich")
t, g = P("<chart>\r\nid=1\r\nsymbol=EURUSD\r\n<window>\r\n<object>\r\nsymbol=GBPUSD\r\n</object>\r\n</window>\r\n</chart>\r\n", "EURUSD.x")
check(g and "symbol=EURUSD.x\r\n<window>" in t and "symbol=GBPUSD\r\n</object>" in t, "mehrere symbol-Zeilen: nur die erste (Chart-Kopf) wird ersetzt")
t, g = P("<chart>\r\nsymbol_xyz=EURUSD\r\n</chart>\r\n", "EURUSD.x")
check(not g, "Zeile „symbol_xyz=“ ist keine symbol-Zeile → bitgleich")
t, g = P("<chart>\r\nid=1\r\n</chart>\r\n", "EURUSD.x")
check(not g and t == "<chart>\r\nid=1\r\n</chart>\r\n", "ohne symbol-Zeile → bitgleich")
t, g = P("<chart>\nsymbol=EURUSD\n</chart>\n", "EURUSD.x")
check(g and t == "<chart>\nsymbol=EURUSD.x\n</chart>\n", "nur LF-Zeilenenden → Symbol ersetzt, Zeilenende bleibt")
alt = provision.symbol_endung
try:
    del provision.symbol_endung
    t, g = P(CHR % "EURUSD", "EURUSD.x")
    check(not g and t == CHR % "EURUSD", "älteres provision.py ohne symbol_endung → bitgleich, kein Absturz")
finally:
    provision.symbol_endung = alt


def profil(tmp, dateien, kodierung):
    """Wegwerf-Datenordner mit Profil „Default“; dateien = {name: text}. → (install_dir, data_dir, {name: pfad})"""
    data = os.path.join(tmp, "data")
    pdir = os.path.join(data, "MQL5", "Profiles", "Charts", "Default")
    os.makedirs(pdir)
    os.makedirs(os.path.join(data, "MQL5", "Experts"))
    open(os.path.join(data, "MQL5", "Experts", provision.EA_NAME + ".ex5"), "wb").close()
    pfade = {}
    for n, text in dateien.items():
        pfade[n] = os.path.join(pdir, n)
        with open(pfade[n], "wb") as f:
            f.write((b"\xff\xfe" + text.encode("utf-16-le")) if kodierung == "utf-16" else text.encode("utf-8"))
    return os.path.join(tmp, "inst"), data, pfade


def lesen(p):
    raw = open(p, "rb").read()
    return (raw[2:].decode("utf-16-le"), raw[:2]) if raw[:2] == b"\xff\xfe" else (raw.decode("utf-8"), b"")


alt_dd = provision.data_dir_for
try:
    for kod in ("utf-16", "utf-8"):
        print(f"2) _inject_ea_into_profile, {kod}")
        with tempfile.TemporaryDirectory() as tmp:   # GFT, frisches Profil
            inst, data, pf = profil(tmp, {"chart01.chr": CHR % "EURUSD", "chart02.chr": CHR % "USDCHF"}, kod)
            provision.data_dir_for = lambda _i, d=data: d
            ok = panel._inject_ea_into_profile("config-gft.json", {"startup_symbol": "EURUSD.x", "snapshot_file": "s.csv"}, inst)
            t1, bom1 = lesen(pf["chart01.chr"])
            t2, _ = lesen(pf["chart02.chr"])
            check(ok and "symbol=EURUSD.x\r\n" in t1 and provision.EA_NAME in t1 and "InpFileName=s.csv" in t1 and t1.rstrip().endswith("</chart>"),
                  "GFT frisch: EA in chart01, Chart-Symbol EURUSD.x")
            check(bom1 == (b"\xff\xfe" if kod == "utf-16" else b"") and t2 == CHR % "USDCHF", "Kodierung/BOM bleibt, chart02 unberührt")
            check(lesen(pf["chart01.chr"] + ".prophos-bak")[0] == CHR % "EURUSD", "Sicherung .prophos-bak trägt den alten Stand")
            vor = open(pf["chart01.chr"], "rb").read()
            check(panel._inject_ea_into_profile("config-gft.json", {"startup_symbol": "EURUSD.x"}, inst) and open(pf["chart01.chr"], "rb").read() == vor,
                  "zweiter Lauf: nichts mehr zu tun, Datei bitgleich")
        with tempfile.TemporaryDirectory() as tmp:   # GFT, Bestand: EA schon auf „EURUSD“ (der Befund)
            kaputt = (CHR % "EURUSD").replace("</chart>", EA + "</chart>")
            inst, data, pf = profil(tmp, {"chart01.chr": kaputt, "chart02.chr": CHR % "USDCHF"}, kod)
            provision.data_dir_for = lambda _i, d=data: d
            ok = panel._inject_ea_into_profile("config-gft.json", {"startup_symbol": "EURUSD.x"}, inst)
            t1, _ = lesen(pf["chart01.chr"])
            check(ok and t1 == kaputt.replace("symbol=EURUSD\r\n", "symbol=EURUSD.x\r\n") and t1.count(provision.EA_NAME) == kaputt.count(provision.EA_NAME),
                  "GFT Bestand: Chart des EA auf EURUSD.x nachgezogen, EA nicht doppelt")
            check(lesen(pf["chart02.chr"])[0] == CHR % "USDCHF" and lesen(pf["chart01.chr"] + ".prophos-bak")[0] == kaputt, "chart02 unberührt, Sicherung da")
        with tempfile.TemporaryDirectory() as tmp:   # alle anderen Firmen: wie vor GT4
            mit_ea = (CHR % "EURUSD").replace("</chart>", EA + "</chart>")
            inst, data, pf = profil(tmp, {"chart01.chr": mit_ea}, kod)
            provision.data_dir_for = lambda _i, d=data: d
            vor = open(pf["chart01.chr"], "rb").read()
            check(panel._inject_ea_into_profile("config-ftmo.json", {}, inst) and open(pf["chart01.chr"], "rb").read() == vor
                  and not os.path.exists(pf["chart01.chr"] + ".prophos-bak"), "ohne startup_symbol, EA schon da: Datei bitgleich, keine Sicherung")
        with tempfile.TemporaryDirectory() as tmp:
            inst, data, pf = profil(tmp, {"chart01.chr": CHR % "EURUSD"}, kod)
            provision.data_dir_for = lambda _i, d=data: d
            ok = panel._inject_ea_into_profile("config-ftmo.json", {"snapshot_file": "s.csv"}, inst)
            t1, _ = lesen(pf["chart01.chr"])
            check(ok and "symbol=EURUSD\r\n" in t1 and provision.EA_NAME in t1, "ohne startup_symbol, frisch: EA injiziert, Chart bleibt EURUSD")
finally:
    provision.data_dir_for = alt_dd

print()
if FEHLER:
    print(f"ROT — {len(FEHLER)} Fehler:")
    for f in FEHLER:
        print("  ✗ " + f)
    sys.exit(1)
print("GRÜN — GT4 Profil-Symbol")

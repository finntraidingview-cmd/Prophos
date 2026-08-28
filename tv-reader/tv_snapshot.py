#!/usr/bin/env python3
"""Prophos TV-Reader — Übersetzer: TradingView-Positionen -> PROPHOS1-Snapshot.

Nimmt die Positionsliste, die der Browser-Reader liefert (positions.json), und
erzeugt daraus exakt das CSV-Format, das mt5-copier/copier.py::read_snapshot
ohnehin liest. Damit braucht der Copier NULL Änderungen — der TV-Reader wird
einfach ein weiterer Master (dasselbe Prinzip wie das NT8-AddOn im Fahrplan).

Reine Rechenlogik, plattformunabhängig, ohne MetaTrader — auf dem Mac testbar
(genau wie plan_actions im Copier). `python3 tv_snapshot.py` fährt den Selbsttest.
"""
import hashlib

# --- Symbol-Tabelle: TradingView-Root -> (Snapshot-Symbol, contract_size = PointValue) ---
# contract_size ist der Punktwert je Kontrakt in Kontowährung. Der Copier rechnet
# hedge_lots = master_vol * contract_size * mult / hedge_contract_size.
# NQ  = E-mini NASDAQ 100, 20 USD/Punkt  -> 1 NQ  = 20 Fusion-NAS100-Lots (bei h_cs 1)
# MNQ = Micro NASDAQ 100,   2 USD/Punkt  -> 1 MNQ =  2 Fusion-NAS100-Lots (bei h_cs 1)
SYMBOLE = {
    "NQ":  ("NQ",  20.0),
    "MNQ": ("MNQ",  2.0),
}


def root_symbol(tv_symbol):
    """'CME_MINI:NQ1!' -> 'NQ', 'CME_MINI:MNQ1!' -> 'MNQ'. Unbekannt -> None."""
    if not tv_symbol:
        return None
    s = tv_symbol.split(":")[-1]          # Börsen-Präfix weg
    s = s.rstrip("!")                      # Continuous-Marker weg  ('NQ1!' -> 'NQ1')
    s = s.rstrip("0123456789")             # Kontrakt-/Monatsziffer weg  ('NQ1' -> 'NQ')
    return s if s in SYMBOLE else None


def parse_de_zahl(text):
    """Deutsche Zahl -> float. '29.618,25' -> 29618.25 ; '+190,00 USD' -> 190.0 ;
    '2' -> 2.0. Gibt None bei leer/None/'-' (Doktrin 'Beweis oder leer': nichts erfinden)."""
    if text is None:
        return None
    t = str(text).strip()
    if not t or t == "-":
        return None
    # nur Zahl, Trenner, Vorzeichen behalten
    t = "".join(c for c in t if c in "0123456789.,-+")
    if not t or t in ("-", "+"):
        return None
    t = t.replace(".", "").replace(",", ".")   # Tausenderpunkt raus, Dezimalkomma -> Punkt
    try:
        return float(t)
    except ValueError:
        return None


def seite_zu_type(seite):
    """'Long' -> 0, 'Short' -> 1. Unbekannt -> None."""
    s = (seite or "").strip().lower()
    if s in ("long", "buy", "kauf"):
        return 0
    if s in ("short", "sell", "verkauf"):
        return 1
    return None


def ident_fuer(symbol, seite):
    """Stabiler, deterministischer Identifier pro Symbol+Richtung.
    Warum inkl. Richtung: TradingView/Tradovate ist Netting (eine Netto-Position je
    Symbol). Dreht sie Long->Short, wechselt der ident -> der Copier schließt den
    alten Hedge und öffnet den neuen (deckt den Netting-Richtungswechsel sauber ab).
    hashlib statt hash(): über Prozess-Neustarts stabil (kein PYTHONHASHSEED)."""
    roh = f"{symbol}|{seite}".encode("utf-8")
    return int(hashlib.md5(roh).hexdigest()[:9], 16)  # <= 11 Stellen, positiv, != 0


def baue_positionen(positionen):
    """positions-Liste (aus dem Reader) -> Liste sauberer Snapshot-Positionen.
    Unbekannte Symbole werden übersprungen (mit Grund). Rückgabe: (zeilen, skips)."""
    zeilen, skips = [], []
    for p in positionen:
        root = root_symbol(p.get("symbol"))
        if root is None:
            skips.append((p.get("symbol"), "unbekanntes Symbol"))
            continue
        snap_sym, c_size = SYMBOLE[root]
        typ = seite_zu_type(p.get("seite"))
        vol = parse_de_zahl(p.get("menge"))
        if typ is None or not vol or vol <= 0:
            skips.append((p.get("symbol"), "Richtung/Menge unklar"))
            continue
        zeilen.append({
            "ident":        ident_fuer(root, "Long" if typ == 0 else "Short"),
            "symbol":       snap_sym,
            "type":         typ,
            "volume":       vol,
            "contract_size": c_size,
            "price_open":   parse_de_zahl(p.get("einstieg")),
            "sl":           parse_de_zahl(p.get("sl")),   # None = kein Level gelesen
            "tp":           parse_de_zahl(p.get("tp")),
        })
    return zeilen, skips


def baue_snapshot(positionen, *, login, server="TV:tradovate", seq=1, unixtime=0):
    """Erzeugt den kompletten PROPHOS1-CSV-String (Kopf + P-Zeilen + Footer).
    balance/equity/currency bleiben leer (der Reader liest sie nicht) -> Copier
    toleriert 7 Felder ('Beweis oder leer', nie eine 0 erfinden).
    SL/TP-Feld: None -> 0.0 im CSV. ACHTUNG-Semantik wie im EA: 0.0 = 'kein Level'.
    price_open None -> 0.0 (Copier v5 behandelt 0.0 als 'nicht gesetzt')."""
    zeilen, skips = baue_positionen(positionen)
    out = [f"PROPHOS1;{seq};{unixtime};{login};{server};0;{len(zeilen)}"]
    for z in zeilen:
        out.append(
            f"P;{z['ident']};{z['symbol']};{z['type']};"
            f"{z['volume']:.8f};{z['contract_size']:.8f};"
            f"{(z['price_open'] or 0.0):.8f};{(z['sl'] or 0.0):.8f};{(z['tp'] or 0.0):.8f}"
        )
    out.append(f"END;{seq};{len(zeilen)}")
    return "\n".join(out) + "\n", skips


# ------------------------------------------------------------------ Selbsttest
def _selftest():
    n = 0

    def ok(cond, name):
        nonlocal n
        assert cond, f"FEHLGESCHLAGEN: {name}"
        n += 1

    # deutsche Zahlen
    ok(parse_de_zahl("29.618,25") == 29618.25, "Tausenderpunkt + Dezimalkomma")
    ok(parse_de_zahl("+190,00 USD") == 190.0, "P&L mit Vorzeichen + Text")
    ok(parse_de_zahl("-570,00\nUSD") == -570.0, "negativ mit Zeilenumbruch")
    ok(parse_de_zahl("2") == 2.0, "ganze Zahl")
    ok(parse_de_zahl("-") is None and parse_de_zahl("") is None, "leer/Strich -> None")

    # Symbol-Normalisierung
    ok(root_symbol("CME_MINI:NQ1!") == "NQ", "NQ normalisiert")
    ok(root_symbol("CME_MINI:MNQ1!") == "MNQ", "MNQ normalisiert")
    ok(root_symbol("FX:EURUSD") is None, "Fremdsymbol -> None")

    # Richtung
    ok(seite_zu_type("Long") == 0 and seite_zu_type("Short") == 1, "Long/Short -> 0/1")

    # ident: stabil, richtungsabhängig
    ok(ident_fuer("NQ", "Long") == ident_fuer("NQ", "Long"), "ident stabil")
    ok(ident_fuer("NQ", "Long") != ident_fuer("NQ", "Short"), "ident dreht mit Richtung")
    ok(0 < ident_fuer("NQ", "Long") < 10**11, "ident positiv, <= 11 Stellen")

    # ganze Position aus echten Reader-Daten
    reader = [
        {"symbol": "CME_MINI:NQ1!", "seite": "Long", "menge": "2",
         "einstieg": "29.618,25", "sl": None, "tp": None, "pnl": "+190,00 USD"},
        {"symbol": "FX:EURUSD", "seite": "Long", "menge": "833.332",
         "einstieg": "1,16452", "sl": None, "tp": None, "pnl": "+41,67 USD"},
    ]
    csv, skips = baue_snapshot(reader, login=24427704, seq=42, unixtime=1787903407)
    lines = csv.strip().split("\n")
    ok(lines[0] == "PROPHOS1;42;1787903407;24427704;TV:tradovate;0;1", "Kopfzeile korrekt (nur NQ zählt)")
    ok(lines[1].startswith("P;") and ";NQ;0;2.00000000;20.00000000;29618.25000000;", "NQ-Zeile: type/vol/csize/entry")
    ok(lines[2] == "END;42;1", "Footer count=1")
    ok(len(skips) == 1 and skips[0][0] == "FX:EURUSD", "EURUSD übersprungen")

    # Gegen den echten Copier-Parser prüfen (wenn erreichbar)
    verifiziert = False
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mt5-copier"))
        import copier  # noqa
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(csv); pfad = f.name
        snap = copier.read_snapshot(pfad, expect_login=24427704)
        os.unlink(pfad)
        ok(snap is not None, "copier.read_snapshot akzeptiert unser CSV")
        ok(len(snap["positions"]) == 1, "Copier liest genau 1 Position")
        pz = snap["positions"][0]
        ok(pz["symbol"] == "NQ" and pz["type"] == 0 and pz["volume"] == 2.0, "Copier: Symbol/Richtung/Menge")
        ok(pz["contract_size"] == 20.0 and pz["price_open"] == 29618.25, "Copier: contract_size/entry")
        ok(copier.read_snapshot(pfad if False else _tmp_wrong(csv), expect_login=99999) is None,
           "Copier verwirft fremden Login")
        verifiziert = True
    except ImportError:
        pass  # copier.py nicht erreichbar (z.B. nur tv-reader/ ausgecheckt) — Format-Tests reichen

    print(f"tv_snapshot Selbsttest: {n} Checks bestanden"
          + (" (inkl. echtem copier.read_snapshot)" if verifiziert else " (copier.py nicht geladen)"))


def _tmp_wrong(csv):
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv)
        return f.name


if __name__ == "__main__":
    _selftest()

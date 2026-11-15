#!/usr/bin/env python3
"""Selbsttest TW4 — Würfel-Ausnahme je ID × Firma × Tag (Finn 16.11.2026 ~03:30 Dubai über den Master: „mach Simon mal rein für heute").

Aufruf:  python3 tools/selftest_tw4_wuerfel_ausnahme.py
Ohne Netz, Platzhalter-IDs. Lädt _ap_norm, den TW1-Block, die TW2-Helfer und den TW4-Block aus app.py (exec mit Stubs) und prüft:
  Diff-Test: ohne Tabelle / leere Tabelle / Lesefehler = bitgleich wie origin-Stand ohne TW4 (alter tw_pause_grund aus git) · Zeile ID × Firma × Tag hebt
  Firmen- UND Konto-Pause auf, nur für diese ID, diese Firma, diesen Tag · firma NULL = alle Firmen der ID · Vergleich nach _ap_norm · Merker 20 s, frisch liest
  neu · gelesen wird nur bei Pause · alle Würfel-Stellen laufen über tw_pause_grund · SQL-Datei (Tabelle, Index, RLS)."""
import hashlib
import os
import re
import subprocess
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-16_wuerfel_ausnahme.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


PLANER = ("challenge_cfd", "challenge_futures", "funded_cfd", "funded_futures", "winning_days")
ZEILEN = {"tw": [], "aus": [], "aus_modus": "ok", "aus_n": 0}


class _Antwort:
    def __init__(self, code, text):
        self.status_code, self.text = code, text


class _HttpFehler(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.response = _Antwort(code, text)


def _sb_select(tab, params):
    if tab == "planer_handel_wuerfel":
        return list(ZEILEN["tw"])
    assert tab == "planer_wuerfel_ausnahme", tab
    assert params.get("select") == "*" and str(params.get("tag", "")).startswith("eq."), params
    ZEILEN["aus_n"] += 1
    if ZEILEN["aus_modus"] == "fehlt":
        raise _HttpFehler(404, '{"message":"relation \\"public.planer_wuerfel_ausnahme\\" does not exist"}')
    if ZEILEN["aus_modus"] == "wirf":
        raise RuntimeError("Netz weg")
    t = params["tag"][3:]
    return [dict(r) for r in ZEILEN["aus"] if str(r.get("tag")) == t]


def _sb_all(tab, params):
    assert tab == "user_settings"
    return []


def _wd_num(v):
    try:
        return None if v is None or v == "" or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


KTX = {"ok": True, "gid_von": {}}


def laden(quelltext, mit_tw4):
    i = quelltext.index("# ══ TW1 HANDELS-WÜRFEL")
    j = quelltext.index('@app.route("/admin/handel-wuerfel"', i)
    i2 = quelltext.index("# ══ TW2 HAND ÜBERSTIMMT DEN PAUSE-TAG")
    j2 = quelltext.index("def tw_pause_dazu(", i2)
    ns = {"hashlib": hashlib, "time": time, "threading": threading, "re": re, "_wd_num": _wd_num, "sb_select": _sb_select, "_sb_all": _sb_all,
          "ap_unt_kontext": lambda frisch=False: KTX, "print": lambda *x, **k: None, "datetime": __import__("datetime").datetime}
    exec(quelltext[quelltext.index("def _ap_norm(name):"):quelltext.index("def ap_regel_finden(")], ns)
    exec(quelltext[i:j], ns)
    exec(quelltext[i2:j2], ns)
    if mit_tw4:
        i4 = quelltext.index("# ══ TW4 WÜRFEL-AUSNAHME")
        j4 = quelltext.index("# ══ RV1 RANGE-WÜRFEL", i4)
        exec(quelltext[i4:j4], ns)
    return ns


A = laden(src, True)
# Vergleichsstand: origin/main, solange TW4 dort noch nicht ist; danach (gepusht) der jetzige Quelltext OHNE den TW4-Block (der Guard in tw_pause_grund
# greift dann nicht) — so bleibt der Test nach dem Push grün und prüft weiter „ohne TW4 = wie vorher“
alt_src = subprocess.run(["git", "-C", WURZEL, "show", "origin/main:app.py"], capture_output=True, text=True).stdout
ALT = laden(alt_src, False) if "def tw_pause_grund(" in alt_src and "# ══ TW4 WÜRFEL-AUSNAHME" not in alt_src else laden(src, False)
check(ALT is not None and "tw_ausnahmen" not in ALT, "Vergleichsstand ohne TW4 geladen")


def uid(x):
    return f"00000000-0000-0000-0000-{x:012d}"


def setze(firma_pct=75, konto_pct=75, aus=None, modus="ok"):
    ZEILEN["tw"] = [{"planer": p, "gruppe": "", "pct": konto_pct} for p in PLANER] + [{"planer": "firma_je_id", "gruppe": "", "pct": firma_pct}]
    ZEILEN["aus"], ZEILEN["aus_modus"] = list(aus or []), modus
    for ns in (A, ALT):
        if ns:
            ns["_tw_hand"].clear()
            ns.get("_tw_aus", {}).clear()
            ns.get("_tw_aus_gut", {}).clear()
            ns["tw_werte"](frisch=True)


FIRMEN = ("Lucid Trading", "Tradeify", "FTMO", "The5%ers", "FundedNext Futures")
TAGE = ("2026-11-16", "2026-11-17", "2026-11-18")
KONTEN = [{"id": uid(1000 + n), "user_id": uid(1 + n % 7), "firm": FIRMEN[n % len(FIRMEN)]} for n in range(140)]


def raster(ns):
    return [(pl, k["id"], t, ns["tw_pause_grund"](pl, k, t)) for pl in PLANER for k in KONTEN for t in TAGE]


# ── 1) Diff-Test: ohne Tabelle, leere Tabelle, Lesefehler = bitgleich ──
if ALT:
    for modus, aus, was in (("fehlt", None, "Tabelle fehlt"), ("ok", [], "Tabelle leer"), ("wirf", None, "Lesefehler"),
                            ("ok", [{"user_id": uid(99), "firma": "Lucid Trading", "tag": "2026-11-16"}], "nur Zeile einer fremden ID")):
        setze(aus=aus, modus=modus)
        neu, alt = raster(A), raster(ALT)
        pausen = sum(1 for z in alt if z[3])
        check(neu == alt and pausen > 100, f"{was}: {len(neu)} Würfe bitgleich mit origin/main ({pausen} Pausen)")

# ── 2) Zeile ID × Firma × Tag ──
SIMON, ANDERE = uid(3), uid(4)
setze(aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}])
lucid_simon = [k for k in KONTEN if k["user_id"] == SIMON and k["firm"] == "Lucid Trading"]
pausiert_vorher = [k for k in lucid_simon if ALT and ALT["tw_pause_grund"]("challenge_futures", k, "2026-11-16")]
check(bool(lucid_simon), f"Testdaten: {len(lucid_simon)} Lucid-Konten der ID")
# erzwinge Firmen-Pause sicher: Firmen-Würfel 0 % → jede ID × Firma pausiert
setze(firma_pct=0, konto_pct=100, aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}])
check(all(A["tw_pause_grund"](pl, k, "2026-11-16") is None for pl in PLANER for k in lucid_simon), "Firmen-Pause (0 %) für ID × Lucid × Tag aufgehoben (alle 5 Planer)")
check(all(A["tw_pause_grund"]("challenge_futures", k, "2026-11-17") for k in lucid_simon), "nächster Tag: wieder Pause (neu gewürfelt)")
andere_firma = [k for k in KONTEN if k["user_id"] == SIMON and k["firm"] != "Lucid Trading"]
check(andere_firma and all(A["tw_pause_grund"]("challenge_cfd", k, "2026-11-16") for k in andere_firma), "andere Firma derselben ID: Pause bleibt")
andere_id = [k for k in KONTEN if k["user_id"] == ANDERE and k["firm"] == "Lucid Trading"]
check(andere_id and all(A["tw_pause_grund"]("challenge_futures", k, "2026-11-16") for k in andere_id), "Lucid einer anderen ID: Pause bleibt")
# Konto-Würfel (TW1) ebenfalls aufgehoben
setze(firma_pct=100, konto_pct=0, aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}])
check(all(A["tw_pause_grund"](pl, k, "2026-11-16") is None for pl in PLANER for k in lucid_simon), "Konto-Pause (TW1 0 %) für ID × Lucid × Tag aufgehoben")
check(all(A["tw_pause_grund"]("challenge_futures", k, "2026-11-16") for k in andere_id), "Konto-Pause anderer ID bleibt")
# master_firm statt firm (Pläne), Groß/Klein + Leerzeichen über _ap_norm
setze(firma_pct=0, konto_pct=100, aus=[{"user_id": SIMON, "firma": "  lucid TRADING ", "tag": "2026-11-16"}])
k0 = lucid_simon[0]
check(A["tw_pause_grund"]("challenge_futures", {"id": k0["id"], "user_id": SIMON, "master_firm": "Lucid Trading"}, "2026-11-16") is None,
      "Firma nach _ap_norm verglichen, master_firm wie firm")
check(A["tw_ausnahme_hat"]({(SIMON, A["_ap_norm"]("FundedNext"))}, SIMON, "FundedNext Futures") is False, "„FundedNext“ ≠ „FundedNext Futures“ (wie TW3)")
# firma NULL = alle Firmen der ID
setze(firma_pct=0, konto_pct=0, aus=[{"user_id": SIMON, "firma": None, "tag": "2026-11-16"}])
alle_simon = [k for k in KONTEN if k["user_id"] == SIMON]
check(all(A["tw_pause_grund"](pl, k, "2026-11-16") is None for pl in PLANER for k in alle_simon), "firma NULL: alle Firmen der ID ohne Würfel")
check(all(A["tw_pause_grund"]("challenge_cfd", k, "2026-11-16") for k in KONTEN if k["user_id"] != SIMON), "firma NULL: andere IDs unverändert")
check(A["tw_ausnahme_hat"]({("*", "*")}, None, "Lucid") is False and A["tw_ausnahme_hat"](set(), SIMON, "Lucid") is False, "ohne ID / leere Menge → keine Ausnahme")
# konto_id (Nachtrag 16.11.2026): nur dieses eine Konto, beide Würfel aus; die übrigen Konten derselben ID × Firma bleiben gewürfelt
MIKE = uid(5)
mike_ftmo = [k for k in KONTEN if k["user_id"] == MIKE and k["firm"] == "FTMO"]
for fp, kp, was in ((0, 100, "Firmen-Pause"), (100, 0, "Konto-Pause")):
    setze(firma_pct=fp, konto_pct=kp, aus=[{"user_id": MIKE, "firma": "FTMO", "konto_id": mike_ftmo[0]["id"], "tag": "2026-11-16"}])
    check(len(mike_ftmo) >= 2 and all(A["tw_pause_grund"](pl, mike_ftmo[0], "2026-11-16") is None for pl in PLANER), f"konto_id: {was} nur für dieses Konto aufgehoben")
    check(all(A["tw_pause_grund"]("challenge_cfd", k, "2026-11-16") for k in mike_ftmo[1:]), f"konto_id: übrige FTMO-Konten der ID behalten die {was}")
    check(A["tw_pause_grund"]("challenge_cfd", mike_ftmo[0], "2026-11-17"), f"konto_id: nächster Tag wieder {was}")
check(A["tw_ausnahme_aus_zeilen"]([{"user_id": MIKE, "firma": None, "konto_id": "k-1", "tag": "2026-11-16"}], "2026-11-16") == {("konto", "k-1")},
      "konto_id-Zeile ohne Firma gilt NICHT für alle Firmen der ID")

# ── 3) Merker, Lesen nur bei Pause, Fehler ──
setze(firma_pct=100, konto_pct=100, aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}])
ZEILEN["aus_n"] = 0
for k in KONTEN:
    A["tw_pause_grund"]("challenge_futures", k, "2026-11-16")
check(ZEILEN["aus_n"] == 0, "alle handeln (100 %) → Ausnahme-Tabelle wird nicht gelesen")
setze(firma_pct=0, konto_pct=100, aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}])
ZEILEN["aus_n"] = 0
for k in KONTEN:
    A["tw_pause_grund"]("challenge_futures", k, "2026-11-16")
check(ZEILEN["aus_n"] == 1, f"Pausen → genau ein Lesen je Tag (Merker 20 s), gelesen {ZEILEN['aus_n']}×")
ZEILEN["aus"] = []
check(A["tw_pause_grund"]("challenge_futures", k0, "2026-11-16") is None, "innerhalb 20 s gilt der Merker")
A["tw_ausnahmen"]("2026-11-16", frisch=True)
check(A["tw_pause_grund"]("challenge_futures", k0, "2026-11-16"), "frisch gelesen (Zeile weg) → Pause wieder da")
setze(firma_pct=0, konto_pct=100, aus=[{"user_id": SIMON, "firma": "Lucid Trading", "tag": "2026-11-16"}], modus="wirf")
A["_tw_aus_gut"].clear()
check(A["tw_pause_grund"]("challenge_futures", k0, "2026-11-16") and A["tw_ausnahmen"]("2026-11-16") == set(), "Lesefehler ohne guten Stand → Würfel gilt (leere Menge)")
check(A["_tw_aus"]["2026-11-16"][0] - time.time() <= 16, "Lesefehler nur 15 s gemerkt")
# Prüfer TW4 SOLLTE 2: kurzer Aussetzer nach gutem Lesen → letzter Stand gilt bis 10 min, danach Würfel; „Tabelle fehlt“ nie
ZEILEN["aus_modus"] = "ok"
A["tw_ausnahmen"]("2026-11-16", frisch=True)
ZEILEN["aus_modus"] = "wirf"
check(A["tw_ausnahmen"]("2026-11-16", frisch=True) == {(SIMON, A["_ap_norm"]("Lucid Trading"))}, "kurzer Lesefehler → Menge = letzter guter Stand")
check(A["tw_pause_grund"]("challenge_futures", k0, "2026-11-16") is None, "kurzer Lesefehler → Ausnahme greift weiter")
A["_tw_aus_gut"]["2026-11-16"] = (time.time() - 601, A["_tw_aus_gut"]["2026-11-16"][1])
check(A["tw_ausnahmen"]("2026-11-16", frisch=True) == set(), "guter Stand älter als 10 min → Würfel gilt")
ZEILEN["aus_modus"] = "ok"; A["tw_ausnahmen"]("2026-11-16", frisch=True); ZEILEN["aus_modus"] = "fehlt"
check(A["tw_ausnahmen"]("2026-11-16", frisch=True) == set(), "Tabelle fehlt → nie der alte Stand")
check(A["tw_ausnahme_aus_zeilen"]([{"user_id": SIMON, "firma": "Lucid", "tag": "2026-11-17"}, "x", {"firma": "Lucid", "tag": "2026-11-16"}], "2026-11-16") == set(),
      "Zeilen anderer Tage / ohne ID / kaputt → ignoriert")
check(A["tw_ausnahmen"]("") == set(), "ohne Tag → leere Menge")

# ── 4) Code-Stellen + SQL ──
pg = src[src.index("def tw_pause_grund("):src.index("def _tw_pct_txt(")]
check('"tw_ausnahmen" in globals() and tw_ausnahme_hat(tw_ausnahmen(tag), uid, firma, (a or {}).get("id"))' in pg and pg.index('if "tw_ausnahmen" in globals()') > pg.index("grund = None"),
      "tw_pause_grund prüft die Ausnahme erst, wenn ein Wurf Pause ergibt")
aufrufe = re.findall(r"tw_pause_grund\(", src)
check(len(aufrufe) >= 6 and "tw_pause_grund(pl, a, tag, w, k)" in src, f"alle Würfel-Stellen (Nachtlauf/Nachplan-Filter/Funded/WD) laufen über tw_pause_grund ({len(aufrufe)} Stellen)")
check("Pause-Tag" not in "".join(eval(src[src.index("AP_NACHPLAN_FEST_GRUENDE = ("):src.index(")", src.index("AP_NACHPLAN_FEST_GRUENDE = (")) + 1].split("=", 1)[1])),
      "„Pause-Tag“ ist kein fester Nachplan-Grund → Takt rechnet nach")
check("create table if not exists public.planer_wuerfel_ausnahme" in sql and "enable row level security" in sql and "firma        text," in sql
      and "tag          date not null" in sql and "coalesce(lower(firma), '*'), coalesce(konto_id::text, '*'), tag" in sql
      and "add column if not exists konto_id uuid" in sql, "SQL: Tabelle, konto_id, eindeutiger Index (firma/konto NULL = *), RLS")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ TW4 alle Prüfungen grün")

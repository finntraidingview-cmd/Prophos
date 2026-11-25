#!/usr/bin/env python3
"""Selbsttest KP6 (Finn 25.11.2026: „Ist der Einkaufszettel bei Emin-IDs auch live?") — der Vorrat-Lauf (Takt/Hand) rechnete nur HT-IDs: _admin_basis
ohne Anfrage = Standard-Sicht „nur HT" (_admin_standard_aus blendet alle Gruppen MIT Verwalter aus), dazu ADMIN_EXCLUDE (Emin selbst). Jetzt rechnet der
Lauf ALLE Unternehmen mit ihren Gruppen-Zielen (KP3) und legt die Gruppen-Zellen getrennt in zellen_gruppen ab — HT-Zahlen (gesamt_score, Trend,
KI-Bot) bleiben unvermischt; die Anzeige filtert wie bisher nach der Sicht der Anfrage.
Rein rechnende Teile echt per AST aus app.py, Wege als Quelltext.  Aufruf:  python3 tools/selftest_kp6_vorrat_unternehmen.py [pfad/zu/app.py]"""
import ast
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "..", "app.py")
SRC = open(APP, encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def zwischen(t, a, b):
    i = t.index(a)
    return t[i:t.index(b, i + len(a))]


NAMEN = {"vorrat_unternehmen_karte", "vorrat_lauf_aus_ids", "vorrat_zellen_trennen", "_admin_verwalter_gruppen_ids"}
ns = {}
exec("\n\n".join(ast.get_source_segment(SRC, n) for n in ast.parse(SRC).body if isinstance(n, ast.FunctionDef) and n.name in NAMEN), ns)
check(all(x in ns for x in NAMEN), "KP6-Bausteine in app.py gefunden")

HT1, HT2, EM, JU, AM, ALT = "u-ht1", "u-ht2", "u-emin", "u-julian", "u-amir", "u-finn-alt"
G_EM, G_HT = "g-emin", "g-ht"
DATEN = {"gruppen": [{"id": G_EM, "verwalter_id": EM, "name": "Emin"}, {"id": G_HT, "verwalter_id": None, "name": "Hermann Technologies"}],
         "mitglieder": [{"gruppe_id": G_EM, "user_id": JU}, {"gruppe_id": G_EM, "user_id": AM}, {"gruppe_id": G_HT, "user_id": HT1}, {"gruppe_id": G_HT, "user_id": HT2}]}
karte = ns["vorrat_unternehmen_karte"](DATEN)
check(karte == {EM: G_EM, JU: G_EM, AM: G_EM}, f"Unternehmens-Karte: Emin (Verwalter) + Mitglieder → Gruppe, HT nie drin → {karte}")
check(set(karte) == ns["_admin_verwalter_gruppen_ids"](DATEN), "dieselbe Menge wie _admin_verwalter_gruppen_ids (Standard-Sicht „nur HT“)")
NAMES = {HT1: "a@x", HT2: "b@x", EM: "emin@x", JU: "j@x", AM: "am@x", ALT: "alt@x"}
aus = ns["vorrat_lauf_aus_ids"](NAMES, {"Emin@X ", "alt@x"}, karte)
check(aus == {ALT}, f"Lauf lässt nur ADMIN_EXCLUDE ohne Gruppe aus (alte Finn-ID) — Emin selbst (Verwalter, eigene Konten) wird gerechnet → {aus}")
check(ns["vorrat_lauf_aus_ids"](NAMES, set(), karte) == set() and ns["vorrat_lauf_aus_ids"]({}, {"x"}, {}) == set(), "ohne Ausblende-Mails / ohne Namen nichts")
Z = [{"user_id": HT1, "firma": "Tradeify"}, {"user_id": JU, "firma": "Lucid Trading", "unternehmen": G_EM}, {"user_id": HT2, "firma": "Lucid Trading"},
     {"user_id": EM, "firma": "FundedNext Futures", "unternehmen": G_EM}]
ht, gr = ns["vorrat_zellen_trennen"](Z)
check([z["user_id"] for z in ht] == [HT1, HT2] and [z["user_id"] for z in gr] == [JU, EM], "Zellen getrennt: HT in zellen, Emin in zellen_gruppen (Reihenfolge bleibt)")

# ── Lauf (Quelltext) ──
lauf = zwischen(SRC, "def vorrat2_rechnen_lauf(", "\ndef vorrat2_lauf(")
check("def vorrat2_rechnen_lauf(quelle, nur_uid=None, alle_unternehmen=True):" in lauf, "Lauf: alle Unternehmen ist der Standard (Takt, Hand-Lauf, Muster-Portfolio je ID)")
check("unternehmen = vorrat_unternehmen_karte(admin_gruppen_daten())" in lauf
      and "excluded_ids = vorrat_lauf_aus_ids(b[\"names\"], ADMIN_EXCLUDE_EMAILS, unternehmen) | (set() if nur_uid else ohne_ids)" in lauf,
      "Lauf: Ausblendung unabhängig von der Sicht der Anfrage — nicht mehr _admin_standard_aus (nur HT), ohne_ids der Vorrat-Seite bleiben")
check("excluded_ids = b[\"excluded_ids\"] | (set() if nur_uid else ohne_ids)" in lauf, "alle_unternehmen=False: wie bisher die Sicht der Anfrage")
check('z["unternehmen"] = unternehmen[uid]' in lauf and "vorrat_zellen_trennen(zellen)" in lauf
      and '"gesamt_score": vorrat_gesamt(zellen_ht)["score"]' in lauf and '"zellen": zellen_ht, "zellen_gruppen": zellen_gr' in lauf,
      "Lauf: Gruppen-Zellen getrennt in zellen_gruppen, gesamt_score nur aus HT")
check("(zellen, []) if (nur_uid or not alle_unternehmen)" in lauf, "Muster-Portfolio einer ID / Sicht-Lauf: alles in zellen (keine Trennung nötig)")
check("ziel_u = vorrat_ziele_fuer(ziele, zg, ug, uid)[f]" in lauf, "Emin-Zellen rechnen mit den Gruppen-Zielen (KP3, unverändert)")
check('((alt.get("ergebnis") or {}).get("zellen_gruppen") or [])' in lauf, "Totband: auch die Gruppen-Zellen des letzten Laufs")
an = zwischen(SRC, "def vorrat2_anhaengen(erg1):", "\ndef ")
check('(e2.get("zellen") or []) + (e2.get("zellen_gruppen") or [])' in an, "Anzeige (Kaufliste/Vorrat): Zellen beider Unternehmen nachschlagen, gezeigt wird nach Sicht")
check('vorrat_gesamt(erg1.get("zellen") or [], heute, trend)' in an and 'ergebnis->gesamt_score' in an, "Gesamt-Score/Trend der Anzeige unverändert (Sicht der Anfrage)")
mp = zwischen(SRC, "def _mp_alle_antwort():", "\ndef ")
check('vorrat2_rechnen_lauf("hand", alle_unternehmen=False)' in mp, "Muster-Portfolio „Alle“: Sicht der Anfrage (Finn = HT, Emin = seine Gruppe) — nie gemischt")
ki = zwischen(SRC, "def admin_vorrat_ki():", "\n# Takt")
check('"select": "id,zellen:ergebnis->zellen"' in ki, "KI-Bot prüft weiter nur gegen HT-Zellen (zellen)")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)

#!/usr/bin/env python3
"""Selbsttest TT1 „Trades pro Tag“ mit Test-IDs statt Testkonten (app.py tt_*, Finn 11.11.2026: „Ich will das mit Test-IDs testen und nicht mit
Test-Konten“ + „erstmal nur für Echo-Konten“ + „Nein, ich will keine Testkonten mehr“).

Aufruf:  python3 tools/selftest_tt1_test_ids.py
Ohne Netz, Platzhalter-IDs. Prüft: tt_param liest test_ids, tt_gilt teilt mit Test-IDs NUR Echo-Konten (mt5v2/mt5) dieser IDs (Futures/Topstep/fremde ID/
Apex/Funded/Schalter aus nie), Testkonten-Weg raus (alter nur_konten-Eintrag ohne Test-IDs sperrt nur); tt_einst_anwenden: nur bekannte HT-IDs,
Speichern von Test-IDs leert nur_konten, „an“ ohne Test-ID nur mit alle_ok; tt_ids_auswahl; ap_planen reicht user_id + route durch, test_n nur bei
Test-IDs; SQL-Datei löst Marco/Simon per Name unter den HT-Planer-IDs auf."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_ws2_tagesteilung as ws2  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


a = ws2.lade()
P, G, E, A = a["tt_param"], a["tt_gilt"], a["tt_einst_anwenden"], a["tt_ids_auswahl"]
ID1, ID2, IDX = ("00000000-0000-0000-0000-0000000000b1", "00000000-0000-0000-0000-0000000000b2", "00000000-0000-0000-0000-0000000000ff")
K1 = "00000000-0000-0000-0000-0000000000c1"
GID = "00000000-0000-0000-0000-0000000000a1"
std = P({})
check(std["test_ids"] == [], "Standard: keine Test-IDs")
check(P({"tagesteilung": {"test_ids": [ID1, "kaputt", 5]}})["test_ids"] == [ID1] and P({"tagesteilung": {"test_ids": "x"}})["test_ids"] == [],
      "tt_param: test_ids nur UUIDs, Kaputtes fällt raus")

pa = dict(std, an=True, test_ids=[ID1])
check(G(pa, "fundednext", None, K1, "phase1", user_id=ID1, route="mt5v2") and G(pa, "the5ers", None, K1, "phase2", user_id=ID1, route="mt5")
      and G(pa, "ftmo", None, K1, "challenge", user_id=ID1, route=None),
      "Test-ID: Echo-Konten (mt5v2 / mt5 / ohne Route = mt5v2) werden geteilt")
check(not G(pa, "tradeify", None, K1, "challenge", user_id=ID1, route="tvv2") and not G(pa, "topstep", None, K1, "challenge", user_id=ID1, route="tsv2"),
      "Test-ID: Futures (Orbit tvv2) und Topstep (tsv2) nie — erstmal nur Echo")
check(not G(pa, "fundednext", None, K1, "phase1", user_id=ID2, route="mt5v2") and not G(pa, "fundednext", None, K1, "phase1", route="mt5v2"),
      "andere ID bzw. ohne user_id: kein Teilen, solange Test-IDs gesetzt sind")
check(not G(dict(pa, an=False), "fundednext", None, K1, "phase1", user_id=ID1, route="mt5v2")
      and not G(pa, "apextrader", None, K1, "challenge", user_id=ID1, route="mt5v2")
      and not G(pa, "fundednext", None, K1, "funded", user_id=ID1, route="mt5v2")
      and not G(dict(pa, firmen=["the5ers"]), "fundednext", None, K1, "phase1", user_id=ID1, route="mt5v2")
      and not G(pa, "fundednext", GID, K1, "phase1", user_id=ID1, route="mt5v2"),
      "Test-ID: Schalter aus global, Apex nie, Funded nie, Firma ohne Häkchen nie, fremdes Unternehmen nie")
check(G(dict(pa, nur_konten=["00000000-0000-0000-0000-000000000009"]), "fundednext", None, K1, "phase1", user_id=ID1, route="mt5v2"),
      "Test-IDs gesetzt → alter Testkonten-Eintrag (nur_konten) spielt keine Rolle")
po = dict(std, an=True)
check(G(po, "tradeify", None, K1, "challenge") and G(po, "tradeify", None, K1, "challenge", user_id=ID2, route="tvv2"),
      "ohne Test-IDs und ohne alten Eintrag: alle Konten der angehakten Firmen (bestätigter Weg „alle“, bitgleich zu vorher)")
check(not G(dict(po, nur_konten=[K1]), "tradeify", None, K1, "challenge", user_id=ID1, route="tvv2")
      and not G(dict(po, nur_konten=[K1]), "fundednext", None, K1, "phase1", user_id=ID1, route="mt5v2"),
      "Testkonten-Weg raus: alter nur_konten-Eintrag ohne Test-IDs teilt NICHTS (auch nicht das eingetragene Konto, nie still alle)")

keys = {"fundednext", "the5ers", "tradeify"}
bek = {ID1, ID2}
r, g = E({"tagesteilung": dict(std, an=True, nur_konten=[K1])}, {"test_ids": [ID1, ID1]}, keys, set(), bek)
check(g is None and r["tagesteilung"]["test_ids"] == [ID1] and r["tagesteilung"]["nur_konten"] == [],
      "neue Test-IDs: gespeichert (ohne Doppel), alte Testkonten geleert")
check(E({}, {"test_ids": [IDX]}, keys, set(), bek)[1].startswith("test_ids: ID") and E({}, {"test_ids": ["x"]}, keys, set(), bek)[1].startswith("test_ids")
      and E({}, {"test_ids": ID1}, keys, set(), bek)[1].startswith("test_ids"),
      "test_ids: nur bekannte HT-Planer-IDs, nur Liste von UUIDs")
r, g = E({"tagesteilung": dict(std, an=True, test_ids=[IDX])}, {"test_ids": [IDX, ID2]}, keys, set(), bek)
check(g is None and r["tagesteilung"]["test_ids"] == [IDX, ID2], "schon gespeicherte Test-ID (nicht mehr im Planer) blockiert das Erweitern nicht")
r, g = E({"tagesteilung": dict(std, an=True, test_ids=[ID1])}, {"test_ids": []}, keys, set(), bek)
check(r is None and "ALLE" in g, "letzte Test-ID weg bei „an“ → abgelehnt (gälte für ALLE Konten)")
r, g = E({"tagesteilung": dict(std, an=True, test_ids=[ID1])}, {"test_ids": [], "alle_ok": True}, keys, set(), bek)
check(g is None and r["tagesteilung"]["test_ids"] == [] and "alle_ok" not in r["tagesteilung"], "… mit alle_ok gespeichert, alle_ok landet nicht in der DB")
r, g = E({"tagesteilung": dict(std, nur_konten=[K1])}, {"an": True, "alle_ok": True}, keys, set(), bek)
check(g is None and r["tagesteilung"]["nur_konten"] == [], "bestätigtes „alle“ leert den alten Testkonten-Eintrag (sonst stünde „alle“ still auf „nichts“)")
check(E({"tagesteilung": dict(std)}, {"an": True}, keys, set(), bek)[1].startswith("ohne Test-ID")
      and E({"tagesteilung": dict(std, nur_konten=[K1])}, {"an": True}, keys, set(), bek)[1].startswith("ohne Test-ID")
      and E({"tagesteilung": dict(std)}, {"an": True, "test_ids": [ID2]}, keys, set(), bek)[1] is None
      and E({"tagesteilung": dict(std, an=True)}, {"anteile": [70, 20, 8, 2]}, keys, set(), bek)[1] is None
      and E({"tagesteilung": dict(std)}, {"an": False}, keys, set(), bek)[1] is None
      and E({}, {"alle_ok": True}, keys, set(), bek)[1] == "tagesteilung = {Feld: Wert}",
      "Schalter an ohne Test-ID nur mit alle_ok (auch mit altem Testkonto); mit Test-ID, anderen Feldern, aus: frei")

aus = A([ID2, ID1], {ID1: "Anna", ID2: "Bert"}, dict(std, test_ids=[ID1, IDX]))
check([x["user_id"] for x in aus] == [ID1, ID2, IDX] and aus[0]["an"] and not aus[1]["an"] and aus[2]["an"] and aus[2]["im_planer"] is False
      and aus[0]["name"] == "Anna", "tt_ids_auswahl: Planer-IDs nach Name, angehakte bleiben sichtbar (auch nicht mehr im Planer)")

src = open(ws2.APP, encoding="utf-8").read()
check('user_id=k["a"].get("user_id"), route=k["regel"].get("route"))' in src
      and '_tt_p.get("test_n") if (_tt_p.get("test_ids") and _tt_p.get("test_n")) else None' in src,
      "ap_planen: user_id + route an tt_gilt, feste Anzahl nur bei Test-IDs")
check('"tagesteilung_ids": (sicher(lambda r: tt_ids_auswahl(reg.get("user_ids") or [], _ap_namen()[0], tt_param(r))) if (admin and not unt) else [])' in src
      and '{str(u) for u in (reg.get("user_ids") or ())})' in src,
      "Einstellungen: tagesteilung_ids nur für Admin/HT, Schreibweg prüft gegen die HT-Planer-IDs")

sql = open(os.path.join(HIER, "..", "sql", "2026-11-11_tt_test_ids.sql"), encoding="utf-8").read()
check("join auth.users u on u.id = any(r.user_ids)" in sql and "in ('marco', 'simon')" in sql and "raise exception" in sql
      and "'{tagesteilung,nur_konten}', '[]'::jsonb" in sql and not __import__("re").search(r"[0-9a-f]{8}-[0-9a-f]{4}-", sql),
      "SQL: Marco/Simon per Name unter den HT-Planer-IDs, Abbruch ohne genau 1 Treffer, nur_konten leer, keine IDs im Repo")

print()
print("selftest_tt1_test_ids: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} rot: " + "; ".join(FEHLER)))
sys.exit(1 if FEHLER else 0)

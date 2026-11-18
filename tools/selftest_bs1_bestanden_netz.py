#!/usr/bin/env python3
"""Selbsttest BS1 (Finn 19.11.2026): Radar → Bestanden ohne stille Leere bei abgebrochenem /admin/handarbeit, Station „Waiting for Payout“
(On Demand) und Knopf „Payout anfragen“ bei Waiting ohne Termin in Admin → Kasse → Payouts. Rechnet hand_radar_waiting aus app.py ohne Netz
und prüft die Bausteine im Frontend (Textprüfung, wie die anderen Radar-Selbsttests).

Aufruf:  python3 tools/selftest_bs1_bestanden_netz.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


src = re.search(r"^def hand_radar_waiting\(.*?(?=^\S)", app, re.S | re.M).group(0)


def _wd_num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


ns = {"_wd_num": _wd_num}
exec(src, ns)
W = ns["hand_radar_waiting"]

k = lambda **o: dict({"id": "k1", "user_id": "u1", "name": "100k 14367821 → Funded · On Demand", "firm": "FundedNext", "account_type": "funded_cfd",
                      "external_id": "14367821", "starting_balance": 100000, "on_demand": True, "waiting_payout_since": "2026-11-18T14:53:14Z",
                      "deaktiviert_at": None, "tv_balance": "104210.5"}, **o)
z = W([k()], set(), {"u1": "Marc"}, set())
check(len(z) == 1 and z[0]["user"] == "Marc" and z[0]["ende4"] == "7821" and z[0]["seit"] == "2026-11-18T14:53:14Z" and z[0]["bal"] == 104210.5 and z[0]["art"] == "waiting",
      "On Demand im Waiting → eine Zeile mit Name, …7821, seit = waiting_payout_since, Balance")
check(W([k(on_demand=False)], set(), {}, set()) == [], "ohne On Demand → keine Zeile")
check(W([k(waiting_payout_since=None)], set(), {}, set()) == [], "ohne Waiting → keine Zeile")
check(W([k(deaktiviert_at="2026-11-17T00:00:00Z")], set(), {}, set()) == [], "deaktiviert → keine Zeile")
check(W([k()], {"k1"}, {}, set()) == [], "archiviert → keine Zeile")
check(W([k()], set(), {}, {"u1"}) == [], "ID ausgeblendet (andere Gruppe) → keine Zeile")
r = W([k(id="a", waiting_payout_since="2026-10-31T08:00:00Z"), k(id="b", waiting_payout_since="2026-11-18T14:53:14Z")], set(), {}, set())
check([x["konto_id"] for x in r] == ["b", "a"], "neueste zuerst")
check('"radar_waiting": radar_wait' in app and 'on_demand="is.true", waiting_payout_since="not.is.null"' in app and "radar_wait = None" in app,
      "Handarbeit liefert radar_waiting (eigene Abfrage, Fehler → None, nie die Bestanden-Liste)")

# Frontend
check("handRadarMerken(d)" in html and "function handRadarGemerkt()" in html and "HAND_MERK_KEY = 'prophos_hand_radar_v1'" in html,
      "gute Antwort wird je ID gemerkt")
check("const fremd = handRadarListe('radar_bestanden')" in html and "const quelle = handRadarListe('radar_waiting')" in html,
      "bstZeilen + wtZeilen lesen über handRadarListe (frisch, sonst gemerkt)")
check("_hand.schnell = setTimeout(() => { _hand.schnell = null; try{ handLaden() }catch(_){} }, 5000)" in html and "_hand.fehlVersuche = 0" in html,
      "Abbruch → Wiederholung nach 5 s, Zähler bei Erfolg zurück")
check("const hinweisZeile = hw ?" in html and "html: hinweisZeile + kaestenWt" in html, "Hinweiszeile über den Stationen, wenn die anderen IDs nicht frisch sind")
check("bstTab(wt, 'Waiting for Payout'" in html and ".wdl-tab-sek-wt{--wdl-sek:#15803d}" in html, "Station Waiting for Payout im Bestanden-Block")
check("const wartetAnf = !!r.waiting_since && !offen" in html and "chip.addEventListener('click', e => { e.stopPropagation(); admAnfrageOeffnen(r) })" in html,
      "Kasse: Waiting ohne Termin + keine offene Anfrage → Knopf auf admAnfrageOeffnen")
m = re.search(r"faellig = c\.tage <= 0 && !offen", html)
check(m is not None, "Termin in der Zukunft bleibt ohne Knopf (faellig-Regel unverändert)")

# handRadarListe: Rückfall-Logik (im Kern nachgerechnet)
def liste(d, gemerkt, feld):
    if d:
        if feld == "radar_bestanden":
            return d.get("radar_bestanden") or (d.get("gruppen") or {}).get("bestanden") or []
        return d.get(feld) if isinstance(d.get(feld), list) else []
    return (gemerkt or {}).get(feld) or []
check(liste(None, {"radar_bestanden": [1, 2]}, "radar_bestanden") == [1, 2], "ohne frische Antwort → gemerkter Stand")
check(liste({"radar_bestanden": [3]}, {"radar_bestanden": [1, 2]}, "radar_bestanden") == [3], "frische Antwort gewinnt")
check(liste(None, None, "radar_waiting") == [], "nichts gemerkt → leer wie bisher")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)

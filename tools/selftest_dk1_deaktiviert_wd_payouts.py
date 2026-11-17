#!/usr/bin/env python3
"""Selbsttest DK1 (Finn 17.11.2026 ~06:35 Dubai: „Bei WD und Payouts etc. sollen deaktivierte Accounts nicht angezeigt und nicht mitgezählt werden.").
Prüft den reinen Filter dk_ohne_deaktiviert, den Rückfall von dk_deaktiviert_anzeige und dass die vier Stellen im Quelltext ihn nutzen
(payout_ready, /admin/wd-heute, wd_liste, /admin/wd-plaene GET „deaktiviert“). Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_dk1_deaktiviert_wd_payouts.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) Filter (rein rechnend)")
Z = [{"account_id": "a", "n": 1}, {"account_id": "b", "n": 2}, {"account_id": "c", "n": 3}]
check([z["n"] for z in app.dk_ohne_deaktiviert(Z, frozenset({"b"}))] == [1, 3], "deaktiviertes Konto fällt raus, Reihenfolge bleibt")
check([z["n"] for z in app.dk_ohne_deaktiviert(Z, frozenset())] == [1, 2, 3], "niemand deaktiviert → alles bleibt")
check(app.dk_ohne_deaktiviert(Z, frozenset()) is not Z, "neue Liste, Eingabe unverändert")
check(app.dk_ohne_deaktiviert(None, frozenset({"a"})) == [], "None → leere Liste")
P = [{"master_account_id": "a", "status": "open"}, {"master_account_id": "a", "status": "review"}, {"master_account_id": "a", "status": "planned"},
     {"master_account_id": "x", "status": "review"}]
r = app.dk_ohne_deaktiviert(P, frozenset({"a"}), feld="master_account_id", offen_behalten=True)
check([(p["master_account_id"], p["status"]) for p in r] == [("a", "open"), ("a", "review"), ("x", "review")],
      f"wd-heute: laufender + zu prüfender Plan bleiben (Abhaken bucht in Finanzen), planned weg ({r})")
r2 = app.dk_ohne_deaktiviert(P, frozenset({"a"}), feld="master_account_id")
check([p["master_account_id"] for p in r2] == ["x"], "ohne offen_behalten fällt auch open raus")
check(app.dk_ohne_deaktiviert([{"account_id": None}], frozenset({"a"})) == [{"account_id": None}], "Zeile ohne Konto-ID bleibt")

print("2) Rückfall bei Lesefehler")
alt = app._ap_deaktiviert_ids
app._ap_deaktiviert_ids = lambda: (_ for _ in ()).throw(RuntimeError("DB weg"))
check(app.dk_deaktiviert_anzeige() == frozenset(), "Lesefehler → leere Menge (Anzeige ungefiltert, kein Abbruch)")
app._ap_deaktiviert_ids = lambda: frozenset({"q"})
check(app.dk_deaktiviert_anzeige() == frozenset({"q"}), "sonst die Menge aus _ap_deaktiviert_ids")
app._ap_deaktiviert_ids = alt

print("3) Quelltext")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("payout_ready = dk_ohne_deaktiviert(payout_ready, dk_deaktiviert_anzeige())" in src, "Admin → Payouts: payout_ready ohne deaktivierte")
check('plaene = dk_ohne_deaktiviert(plaene, dk_deaktiviert_anzeige(), feld="master_account_id", offen_behalten=True)' in src, "/admin/wd-heute ohne deaktivierte (open bleibt)")
check('str(p.get("master_account_id") or "") not in dk_ids' in src and "dk_ids = dk_deaktiviert_anzeige()" in src, "wd_liste (WD-Statistik) ohne deaktivierte")
check('"deaktiviert": sorted(i for i in deakt if sicht_get is None or deakt_uid.get(i) in sicht_get)' in src, "/admin/wd-plaene GET liefert deaktiviert, nur der eigenen Sicht")
check(src.find("deakt_uid = {") < src.find('"deaktiviert": sorted(i for i in deakt') and src.find("sicht_get = _admin_sicht()") < src.find('"deaktiviert": sorted(i for i in deakt'),
      "deakt_uid und sicht_get stehen vor der Antwort")
# Summen des Kapitels (Kauf, Payouts, Master-P&L) bleiben: der Filter sitzt nur an der wd_liste-Bedingung
i = src.find("dk_ids = dk_deaktiviert_anzeige()")
check(src.count("dk_ids") == 2 and i > 0, "dk_ids nur an wd_liste (Kapital/Kosten/Payouts unberührt)")
h = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("const dkAus = !!a.deaktiviertAt" in h and "let payoutHtml = (dkAus && !dkPoOffen) ? ''" in h, "Accounts: kein Payout-/Ziel-Chip an deaktivierten Konten, offene Anfrage bleibt")
check("for(const k of konten) if(deakt.has(k.id)) k.deaktiviert = true" in h and "&& !deakt(k))" in h, "Farmer: Marke + Ausblenden in der ID-Tabelle")
check("k.status !== 'open' && k.status !== 'review' && !(k.status === 'planned' && k.gestartet)" in h, "Farmer: laufend/review/gestartet bleiben sichtbar")
print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)

#!/usr/bin/env python3
"""Selbsttest DK1 (Finn 17.11.2026 ~06:35 Dubai: „Bei WD und Payouts etc. sollen deaktivierte Accounts nicht angezeigt und nicht mitgezählt werden.").
Prüft den reinen Filter dk_ohne_deaktiviert, den Rückfall von dk_deaktiviert_anzeige und dass die Stellen im Quelltext ihn nutzen
(payout_ready, /admin/wd-heute, /admin/wd-plaene GET „deaktiviert“) — und dass die WD-Statistik (wd_liste) ihn NICHT nutzt (DK1b). Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_dk1_deaktiviert_wd_payouts.py"""
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
# DK1c (Prüfer S2 17.11.2026): completed/cancelled mit nicht geschlossenem Fusion-Hedge bleibt — die 20-s-Wächter lesen /admin/wd-heute
H = [{"master_account_id": "a", "status": "completed", "mt5_baseline": {"hedge": {"status": "offen"}}},
     {"master_account_id": "a", "status": "cancelled", "mt5_baseline": {"hedge": {"status": "schliesst"}}},
     {"master_account_id": "a", "status": "completed", "mt5_baseline": {"hedge": {"ticket": 1}}},
     {"master_account_id": "a", "status": "completed", "mt5_baseline": {"hedge": {"status": "geschlossen"}}},
     {"master_account_id": "a", "status": "completed", "mt5_baseline": {}},
     {"master_account_id": "a", "status": "completed", "mt5_baseline": None}]
rh = app.dk_ohne_deaktiviert(H, frozenset({"a"}), feld="master_account_id", offen_behalten=True)
check([((p.get("mt5_baseline") or {}).get("hedge") or {}).get("status", "ohne") for p in rh] == ["offen", "schliesst", "ohne"],
      f"Hedge offen/schliesst/ohne Status bleibt, geschlossen bzw. kein Hedge fällt raus ({len(rh)})")
check(app.dk_hedge_nicht_zu({"mt5_baseline": {"hedge": {"status": "fehler"}}}) is True and app.dk_hedge_nicht_zu({}) is False
      and app.dk_hedge_nicht_zu({"mt5_baseline": "kaputt"}) is False, "dk_hedge_nicht_zu: fehler = nicht zu, ohne/kaputte Baseline = kein Hedge")
check(len(app.dk_ohne_deaktiviert(H, frozenset({"a"}), feld="master_account_id")) == 0, "ohne offen_behalten zählt auch der Hedge nicht")
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
# DK1b (Finn 17.11.2026: „Nein, Statistik behalten."): wd_liste filtert NICHT nach deaktiviert
check("dk_ids" not in src and "DK1b (Finn 17.11.2026" in src, "wd_liste (WD-Statistik) behält historische WDs deaktivierter Konten")
check('"deaktiviert": sorted(i for i in deakt if sicht_get is None or deakt_uid.get(i) in sicht_get)' in src, "/admin/wd-plaene GET liefert deaktiviert, nur der eigenen Sicht")
check(src.find("deakt_uid = {") < src.find('"deaktiviert": sorted(i for i in deakt') and src.find("sicht_get = _admin_sicht()") < src.find('"deaktiviert": sorted(i for i in deakt'),
      "deakt_uid und sicht_get stehen vor der Antwort")
h = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("const dkAus = !!a.deaktiviertAt" in h and "let payoutHtml = (dkAus && !dkPoOffen) ? ''" in h, "Accounts: kein Payout-/Ziel-Chip an deaktivierten Konten, offene Anfrage bleibt")
check("for(const k of konten) if(deakt.has(k.id)) k.deaktiviert = true" in h and "&& !deakt(k))" in h, "Farmer: Marke + Ausblenden in der ID-Tabelle")
check("k.status !== 'open' && k.status !== 'review' && !(k.status === 'planned' && k.gestartet)" in h, "Farmer: laufend/review/gestartet bleiben sichtbar")
check("&& !(k.hedgeSt && k.hedgeSt !== 'geschlossen')" in h and "hedgeSt: p.anz_hedge || null" in h and '"anz_hedge:mt5_baseline->hedge->>status",' in src,
      "Farmer: Plan mit nicht geschlossenem Hedge bleibt (DK1c, Alias aus GET /admin/wd-plaene)")
print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)

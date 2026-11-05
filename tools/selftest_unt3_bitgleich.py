#!/usr/bin/env python3
"""Selbsttest UNT3 (Phase 2 „Regel je Unternehmen“): Vorher/Nachher-Vergleich ALLER Konten beider Unternehmen mit Live-Daten.
Vorher = jede Konto-Rechnung mit der Standard-Regel (wie bis .2065: auto_plan_regeln id=1 für alle), Nachher = mit ap_unt_firmen (Regel des
Unternehmens der ID). Gerechnet je Konto: Kernwerte (ap_kw_param), Kontowert, Boden, Ziel (Ziel-Wache), Consistency-Ziel (M2), Blow-Prüfung,
Radar-Liq-Boden, Konto-Stand-Zeile, Echo-Hedge zählt?, DD-Vorschlag, Vorrat-Stufen.
(A) Live-Stand (Emin ohne Abweichung, firmen_modell wie live) → alles bitgleich. (B) Emin mit Abweichung (Ziel %/Max DD Lucid 50k) → nur Emins
Lucid-Konten ändern sich, kein HT-Konto. Live-Daten: UNT3_LIVE=<json> (SELECT-Auszug, nicht im Repo — enthält Konten); ohne → übersprungen.
Aufruf: UNT3_LIVE=…/unt3_live.json PROPHOS_FRONTEND=1 python3 tools/selftest_unt3_bitgleich.py"""
import copy
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


PFAD = os.environ.get("UNT3_LIVE")
if not PFAD or not os.path.exists(PFAD):
    print("UNT3_LIVE fehlt — Live-Vergleich übersprungen (SELECT-Auszug, siehe Kopf)")
    sys.exit(0)
D = json.load(open(PFAD, encoding="utf-8"))
STD = (D["regeln"] or {}).get("firmen") or []
GID = str(D["gruppe"]["gruppe_id"])
GRUPPE = set(str(u) for u in (D.get("mitglieder") or [])) | {str(D.get("verwalter"))}
KONTEN = D["konten"]
FM = D["gruppe"].get("firmen_modell") or {}


def ktx(abw):
    return {"ok": True, "gid_von": {u: GID for u in GRUPPE}, "zeilen": {GID: {"gruppe_id": GID, "regeln": abw, "firmen_modell": FM}},
            "ht": frozenset(str(u) for u in D.get("user_ids") or []), "memo": {}}


def bal_von(a):
    b = app.acc_balance_wahl(a, {}, {})[0]
    return float(b) if b is not None else (float(a["starting_balance"]) if a.get("starting_balance") else None)


def rechnen(a, firmen):
    """Alle Konto-Rechnungen, die UNT3 umstellt, mit dieser Firmen-Liste → dict (JSON-vergleichbar)."""
    bal = bal_von(a)
    regel = app.ap_regel_finden(firmen, a.get("firm"))
    typ = a.get("account_type")
    out = {"kw": app.ap_kw_param(regel)}
    if bal is not None:
        rk = app.ap_regel_konto(regel, a, bal) if regel else None
        out["kontowert"] = app.ap_kontowert_konto(a, bal, firmen)
        out["boden"] = app.ap_boden_sicher(firmen, a, bal, {})
        out["ziel"] = app.zw_ziel(rk, typ, bal) if rk else None
        out["cons"] = app.zw_cons_ziel(regel, a, bal, {"2026-11-03": 900.0, "2026-11-04": 300.0}) if regel and app.zw_cons_moeglich(regel, a) else None
        out["blow"] = app.ap_ende_unter_boden(app.ap_regel_konto(regel, a, bal), typ, bal, bal - 1500.0) if regel else None
        out["stand"] = app.ap_konten_stand_zeile(a, regel, bal, {"2026-11-04": 500.0})
    out["liq"] = app.liq_boden_kernwerte(None, a, typ, False, firmen)
    out["echo"] = app.eh_plan_zaehlt(a, regel)
    out["dd"] = app.konto_dd_aus_regel(firmen, a.get("firm"), app._wd_konto_groesse(a))
    out["vorrat"] = app.vorrat_stufen_aus_kernwerten(regel, dict(app.VORRAT2_STD)) if regel else None
    return json.loads(json.dumps(out, sort_keys=True, default=str))


def vergleich(abw):
    k = ktx(abw)
    anders = {}
    for a in KONTEN:
        vor = rechnen(a, STD)
        nach = rechnen(a, app.ap_unt_firmen(a.get("user_id"), STD, k))
        if vor != nach:
            anders[a["id"]] = (a, [x for x in vor if vor.get(x) != nach.get(x)])
    return anders


print(f"Live: {len(KONTEN)} Konten (Challenge/Phase 1/Phase 2), davon {sum(1 for a in KONTEN if str(a['user_id']) in GRUPPE)} in Emins Gruppe, "
      f"{len(STD)} Firmen-Regeln, Gruppe: Abweichung {D['gruppe'].get('regeln')!r}, firmen_modell {FM}")
print("A) Live-Stand: Emin ohne Abweichung")
anders = vergleich(D["gruppe"].get("regeln") or {})
for aid, (a, felder) in list(anders.items())[:10]:
    print(f"     anders: {a.get('firm')} {a.get('name')} ({'Emin' if str(a['user_id']) in GRUPPE else 'HT'}): {felder}")
check(not anders, f"alle {len(KONTEN)} Konten beider Unternehmen bitgleich ({len(anders)} anders)")
check(app.ap_unt_firmen("ht-id", STD, ktx({})) is STD and app.ap_unt_firmen(next(iter(GRUPPE)), STD, ktx({})) is not STD,
      "HT-ID bekommt dieselbe Liste (Objekt), Emin seine (firmen_modell gesetzt) — Inhalt der Rechnungen trotzdem gleich")

print("B) Emin mit Abweichung: Lucid Ziel 8 % (wirksamer Pfad wie in den Einstellungen), Max DD 50k 2.500 $")
lu = next((f for f in STD if (f.get("namen") or [None])[0] == "lucidtrading"), None)
jg = ((lu or {}).get("je_groesse") or {}).get("50000") or {}
abw_l = {}
if isinstance((lu or {}).get("ziel_pct"), dict) and "challenge" in lu["ziel_pct"]:
    abw_l["ziel_pct"] = {"challenge": 8}            # ziel_pct am Knoten gewinnt vor phasen.challenge.ziel_pct (E3) — das ist das Feld der Einstellungen
if "dd_usd" in jg:
    abw_l["je_groesse"] = {"50000": {"dd_usd": 2500}}
abw = {"firmen": {"lucidtrading": abw_l}}
anders = vergleich(abw)
ht_anders = [a for a, _f in anders.values() if str(a["user_id"]) not in GRUPPE]
em = [a for a, _f in anders.values() if str(a["user_id"]) in GRUPPE]
em_lucid = [a for a in KONTEN if str(a["user_id"]) in GRUPPE and app.ap_regel_finden(STD, a.get("firm")) is lu]
print(f"     Abweichung {json.dumps(abw)} → {len(em)} Emin-Konten anders, {len(ht_anders)} HT-Konten anders; Emins Lucid-Konten: {len(em_lucid)}")
check(not ht_anders, "kein HT-Konto ändert sich durch Emins Abweichung")
check(em and {a["id"] for a in em} <= {a["id"] for a in em_lucid}, f"nur Emins Lucid-Konten rechnen mit der Abweichung ({len(em)}/{len(em_lucid)})")
for a in em[:3]:
    v, n = rechnen(a, STD), rechnen(a, app.ap_unt_firmen(a["user_id"], STD, ktx(abw)))
    print(f"     {a.get('name')}: Ziel {(v.get('ziel') or [None])[0]} → {(n.get('ziel') or [None])[0]}, Kontowert-Satz {(v.get('kontowert') or {}).get('satz_eur_pro_usd')} → "
          f"{(n.get('kontowert') or {}).get('satz_eur_pro_usd')}, Boden {(v.get('boden') or {}).get('boden')} → {(n.get('boden') or {}).get('boden')}")
z50 = [a for a in em if app._wd_konto_groesse(a) == 50000 and a.get("account_type") == "challenge"]
if z50:
    a = z50[0]; n = rechnen(a, app.ap_unt_firmen(a["user_id"], STD, ktx(abw)))
    check((n.get("ziel") or [0])[0] == 54000.0 and (n.get("boden") or {}).get("boden") is not None,
          f"Emins Lucid 50k: Ziel 54.000 (8 %), Boden/Kontowert mit Max DD 2.500 ({(n.get('ziel') or [None])[0]}, {(n.get('boden') or {}).get('boden')})")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)

#!/usr/bin/env python3
"""Selbsttest Probelauf über alle IDs (app.py, PROBELAUF-ALLE-IDS, 07.10.2026; Finn 04:08 dt: „alle IDs einfach als geplant
reinpacken, sodass ich grob sehe, wie dann geplant wird und das Long-Short-Verhältnis ausgeglichen wird") — ohne Netz.

Aufruf:  python3 tools/selftest_auto_alle_ids.py
Lädt die Auto-Planer-Funktionen wie selftest_auto_delta (per Quelltext aus app.py) und ergänzt die neuen Helfer. Geprüft:
ap_ids_modus (ohne ids wie bisher · falscher Wert 400 · Nicht-Admin 403 · Admin + trocken:false ignoriert ids), ap_ids_laden
(IDs außerhalb der Regel-IDs kommen dazu, ausgeblendete Personen fehlen, nur AP_TYPEN), ap_ids_benutzt (eindeutig, nach Name),
und ap_planen mit ids="alle" gegen eine nachgebaute DB (Platzhalter-IDs, keine echten Konten): fremde ID wird geplant,
ids_benutzt[] mit Namen, nichts geschrieben (kein Plan, kein Protokoll); ohne ids wie bisher; trocken:false ignoriert ids.
Dazu (B2) ap_eingriff_sicht: Bestätigen/Zurücknehmen/Löschen für alle IDs durch Admin und jeden Planer-Login, „nur eigene“ und
Fremde nur die eigene ID; Guard-Bedingungen von ap_eingriff_filter unverändert."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402  (Lader, Fixture und DB-Stub wiederverwenden)

U1, U2, U3 = sd.U1, sd.U2, sd.U3
U4 = "00000000-0000-0000-0000-0000000000a4"      # ausgeblendete Person (ADMIN_EXCLUDE_EMAILS)
U5 = "00000000-0000-0000-0000-0000000000a5"      # nur ein Winning-Days-Konto → kein Konto in AP_TYPEN


def lade():
    a = sd.lade()
    src = open(sd.APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(r"^AP_IDS_ALLE = .*$", src, re.M).group(0)]
                   + [block(f) for f in ("ap_ids_modus", "ap_ids_alle", "ap_ids_laden", "ap_ids_benutzt", "ap_eingriff_sicht")]), a)
    return a


def in_liste(wert):
    """PostgREST „in.(a,b)" → Liste, sonst None."""
    return re.findall(r"[\w-]+", wert[4:-1]) if wert and wert.startswith("in.(") else None


def db_stubs(a, jetzt):
    """Stub wie selftest_auto_delta, aber mit user_id-Filter (den braucht der Alle-Modus) und drei weiteren IDs."""
    reg, geschrieben = sd.db_stubs(a, jetzt)
    konten, bal, offen = sd.fixture(jetzt)
    konten += [
        {"id": "k-8", "user_id": U3, "name": "TDFY C", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000008"},
        {"id": "k-9", "user_id": U4, "name": "TDFY D", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000009"},
        {"id": "k-10", "user_id": U5, "name": "TDFY E", "firm": "Tradeify", "account_type": "winning_days", "external_id": "TDFY-000010"},
    ]
    bal.update({"k-8": 150000, "k-9": 150000, "k-10": 150000})
    inserts = []

    def _sb_all(table, params):
        uids = in_liste(params.get("user_id", ""))
        if table == "accounts":
            ids, typen = in_liste(params.get("id", "")), params.get("account_type")
            return [dict(k) for k in konten if (ids is None or k["id"] in ids) and (uids is None or k["user_id"] in uids)
                    and (not typen or k["account_type"] in typen)]
        if table == "trade_plans":
            st = params.get("status")
            rows = offen if st == "eq.open" else [] if st else offen
            return [dict(p) for p in rows if uids is None or p["user_id"] in uids]
        if table == "firm_specs":
            return [{"user_id": U1, "name": "FundedNext", "ppl": "10.0000", "symbol": None, "unit": "Lots"},
                    {"user_id": U2, "name": "The5%ers", "ppl": "1.0000", "symbol": None, "unit": "Lots"},
                    {"user_id": U2, "name": "Tradeify", "ppl": "2.0000", "symbol": "MNQ", "unit": "Kontrakte"}]
        return []

    class R:                      # Fake-Antwort für DELETE/POST beim Anlegen (der Delta-Stub kennt kein raise_for_status)
        status_code = 201

        def raise_for_status(self):
            return None

    a.update({
        "_sb_all": _sb_all,
        "_sb_anfrage": lambda *args, **k: (geschrieben["post"].append((args, k)), R())[1],
        "sb_insert": lambda table, body: (inserts.append((table, body)), {"id": 1})[1],
        "_ap_namen": lambda: ({U1: "Eins", U2: "Zwei", U3: "Drei", U4: "Vier", U5: "Fünf"}, {U4}),
        "acc_balance_wahl": lambda k, e, d: (bal.get(str((k or {}).get("id"))), "USD", "TV", "2999-01-01"),
    })
    return reg, geschrieben, inserts


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    # ── A ap_ids_modus: Parameter der Route ───────────────────────────────────────────────────────────────────────────
    m = a["ap_ids_modus"]
    check(m({"trocken": True}, True) == (None, None) and m({}, False) == (None, None), "ohne ids: wie bisher (Admin und Nicht-Admin)")
    check(m({"trocken": True, "ids": " Alle "}, True) == ("alle", None), "Admin + trocken + ids alle → alle (Groß/Klein, Leerzeichen egal)")
    check(m({"trocken": False, "ids": "alle"}, True) == (None, None) and m({"ids": "alle"}, True) == (None, None),
          "Admin + trocken:false (oder ohne trocken): ids ignoriert")
    f = m({"trocken": True, "ids": "alle"}, False)
    check(f == (None, ("Probelauf über alle IDs nur für Admins", 403)), f"Nicht-Admin + ids alle → 403 ({f[1]})")
    check(m({"trocken": False, "ids": "alle"}, False)[1][1] == 403, "Nicht-Admin auch mit trocken:false → 403")
    check(m({"trocken": True, "ids": "u1,u2"}, True)[1] == ("ids = alle", 400), "anderer Wert → 400")
    check(a["ap_ids_alle"]("alle", True) is True and a["ap_ids_alle"]("alle", False) is False
          and a["ap_ids_alle"](None, True) is False and a["ap_ids_alle"]("ALLE", 1) is True, "ap_ids_alle: nur alle + trocken")

    # ── B ap_ids_benutzt rein rechnend ──────────────────────────────────────────────────────────────────────────────
    b = a["ap_ids_benutzt"]([{"user_id": "x", "user": "Zed"}], [{"user_id": "y", "user": "anna"}, {"user_id": "x", "user": "Zed"}])
    check(b == [{"user_id": "y", "user": "anna"}, {"user_id": "x", "user": "Zed"}], "ids_benutzt: eindeutig, nach Name sortiert (Groß/Klein egal)")
    check(a["ap_ids_benutzt"]([{"user_id": "q"}], [], {"q": "Quell"}) == [{"user_id": "q", "user": "Quell"}], "Name aus der namen-Karte, wenn die Zeile keinen trägt")
    check(a["ap_ids_benutzt"]([], []) == [] and a["ap_ids_benutzt"](None, None) == [], "leer → leer")

    # ── B2 Bestätigen für alle IDs (Finn 07.10.2026 05:16: „jeden einzelnen Trade bestätigen können. Fertig.") ──────────────
    es, ef = a["ap_eingriff_sicht"], a["ap_eingriff_filter"]
    check(es(True, "adm", False, False) is None and es(True, "adm", False, True) == "adm", "Admin: alle IDs — mit „nur eigene“ nur die eigene")
    check(es(False, "jac", True, False) is None, "Planer-Login (in user_ids) ohne „nur eigene“: alle IDs")
    check(es(False, "jac", True, True) == "jac", "Planer-Login mit „nur eigene“: nur die eigene ID")
    check(es(False, "xyz", False, False) == "xyz", "Fremder Login (nicht im Planer): nur die eigene ID → fremder Plan = 403 in der Route")
    pid = "00000000-0000-0000-0000-00000000aa01"
    prm, bod, art = ef("bestaetigen", [pid], es(False, "jac", True, False))
    check(prm is not None and "user_id" not in prm and bod and "auto_bestaetigt_at" in bod and art == "patch",
          "Planer-Login: Guard ohne user_id-Filter → fremder Vorschlag wird bestätigt")
    prm, _b, _a = ef("bestaetigen", [pid], es(False, "jac", True, True))
    check(prm is not None and prm.get("user_id") == "eq.jac", "„nur eigene“: Guard mit user_id = eigene ID")
    check(ef("loeschen", [pid], None)[2] == "delete" and ef("zurueck", [pid], None)[1] == {"auto_bestaetigt_at": None},
          "Guard-Bedingungen unverändert (loeschen = delete, zurueck setzt auto_bestaetigt_at null)")

    # ── C Rauch-Lauf ohne Netz ──────────────────────────────────────────────────────────────────────────────────────
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)     # morgen: unabhängig von der Uhrzeit
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    tag_s = tag.strftime("%Y-%m-%d")
    reg, geschrieben, inserts = db_stubs(a, jetzt)
    check(a["ap_ids_laden"]() == sorted([U1, U2, U3]), "ap_ids_laden: Regel-IDs + fremde ID, ohne ausgeblendete Person, ohne reine WD-ID")
    check(a["ap_ids_laden"](set()) == sorted([U1, U2, U3, U4]), "ap_ids_laden ohne Ausblendung: auch die ausgeblendete Person")

    erg = a["ap_planen"](tag_s, trocken=True, seed=4711, ids="alle")
    check(erg.get("ok") and not erg.get("probelauf_fehler"), f"Probelauf alle IDs läuft durch ({erg.get('msg') or erg.get('probelauf_fehler') or 'ok'})")
    ids_g = {g["user_id"] for g in erg.get("geplant", [])}
    ids_a = {x["user_id"] for x in erg.get("ausgelassen", [])}
    check(U3 in ids_g and any(g["konto_id"] == "k-8" for g in erg["geplant"]), "fremde ID (nicht in user_ids) wird im Alle-Modus geplant")
    check(U1 in ids_g and U2 in ids_g, "Regel-IDs weiter dabei")
    check(U4 not in ids_g | ids_a and U5 not in ids_g | ids_a, "ausgeblendete Person und reine WD-ID fehlen")
    k8 = next((g for g in erg["geplant"] if g["konto_id"] == "k-8"), {})
    check(k8.get("richtung") == "sell", f"Richtungsschutz gilt auch für die fremde ID (Tradeify läuft short → k-8 {k8.get('richtung')})")
    ib = erg.get("ids_benutzt")
    check(isinstance(ib, list) and {x["user_id"] for x in ib} == {U1, U2, U3} and [x["user"] for x in ib] == ["Drei", "Eins", "Zwei"],
          f"ids_benutzt[] = die drei IDs mit Namen, nach Name sortiert ({[x.get('user') for x in ib or []]})")
    check(all("user_id" in z and "user" in z for z in erg["geplant"] + erg["ausgelassen"]), "jede Zeile trägt user_id und user")
    check(all(k in erg for k in ("tranchen", "ausgleich", "einsatz", "fingerabdruck", "seed")), "Antwort wie der normale Probelauf (tranchen, ausgleich, einsatz …)")
    check(not geschrieben["post"] and not geschrieben["patch"] and not inserts, "Alle-Modus schreibt nichts: kein Plan, kein Protokoll")
    check(erg["fingerabdruck"] == a["ap_planen"](tag_s, trocken=True, seed=4711, ids="alle")["fingerabdruck"], "gleicher seed → gleicher Fingerabdruck")

    erg0 = a["ap_planen"](tag_s, trocken=True, seed=4711)
    check(erg0.get("ok") and U3 not in {g["user_id"] for g in erg0["geplant"]} and "ids_benutzt" not in erg0,
          "ohne ids: nur Regel-IDs, kein ids_benutzt")
    check(erg0["fingerabdruck"] != erg["fingerabdruck"], "Alle-Modus ist ein anderer Stand (Fingerabdruck weicht ab)")

    reg, geschrieben, inserts = db_stubs(a, jetzt)
    erg1 = a["ap_planen"](tag_s, trocken=False, seed=4711, ids="alle")
    zeilen = [z for args, k in geschrieben["post"] if args[0] == "POST" for z in (k.get("json") or [])]
    check(erg1.get("ok") and "ids_benutzt" not in erg1 and zeilen and all(z["user_id"] in (U1, U2) for z in zeilen),
          f"trocken:false: ids ignoriert — angelegt nur für Regel-IDs ({len(zeilen)} Zeilen, keine fremde ID)")
    check(inserts and inserts[0][0] == "auto_plan_lauf", "Anlegen protokolliert wie bisher")

    print("ALLES OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

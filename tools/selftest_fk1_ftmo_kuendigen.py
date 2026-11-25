#!/usr/bin/env python3
"""Selbsttest FK1 Backend (Finn 25.11.2026: FTMO-Futures-Challenges verlängern sich nach einem Monat automatisch, auch geblowte → „Abo kündigen").
Rein rechnend echt per AST aus app.py: fk1_verlaengerung (Kauf + n × 30 Tage, nächster ab heute), fk1_faelle (nur FTMO Futures · challenge ·
Archiv reason 'blown' · ohne abo_gekuendigt_at; ≤ 3 Tage rot); Route /konto/abo-kuendigen als Quelltext (Gate, Marke, ohne Spalte leer).
Aufruf:  python3 tools/selftest_fk1_ftmo_kuendigen.py [pfad/zu/app.py]"""
import ast
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "..", "app.py")
SRC = open(APP, encoding="utf-8").read()
SQL = open(os.path.join(HIER, "..", "sql", "2026-11-25_fk1_ftmo_futures_kuendigen.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


NAMEN = {"pa1_iso", "FK1_FIRMA", "FK1_ZYKLUS_T", "FK1_ROT_T", "fk1_verlaengerung", "fk1_faelle", "fk1_archiv_je_konto"}
teile = []
for n in ast.parse(SRC).body:
    if isinstance(n, ast.FunctionDef) and n.name in NAMEN:
        teile.append(ast.get_source_segment(SRC, n))
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMEN for t in n.targets):
        teile.append(ast.get_source_segment(SRC, n))
ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "ZoneInfo": ZoneInfo}
exec("\n\n".join(teile), ns)
check(all(x in ns for x in NAMEN), "FK1-Bausteine in app.py gefunden")
v, f = ns["fk1_verlaengerung"], ns["fk1_faelle"]

H = date(2026, 11, 25)
check(v(date(2026, 11, 1), H) == date(2026, 12, 1), "Kauf 01.11. → verlängert 01.12.")
check(v(date(2026, 10, 1), H) == date(2026, 11, 30), "Kauf 01.10. → 31.10. vorbei → nächste 30.11.")
check(v(date(2026, 10, 26), H) == date(2026, 11, 25), "am Verlängerungstag selbst: heute")
check(v(date(2026, 11, 25), H) == date(2026, 12, 25), "heute gekauft → in 30 Tagen (n ≥ 1)")
check(v(date(2026, 8, 1), H) == date(2026, 11, 29), "mehrere Zyklen: 31.08., 30.09., 30.10., 29.11.")
check(v(None, H) is None, "ohne Kauftag nichts")

U1, U2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
K = lambda i, **kw: dict({"id": f"k{i}", "user_id": U1, "name": f"50k FTMO11076{i} → Challenge", "firm": "FTMO Futures", "account_type": "challenge",   # noqa: E731
                          "external_id": f"FTMO11076{i}", "created_at": "2026-11-01T10:00:00+00:00", "abo_gekuendigt_at": None}, **kw)
konten = [K(1), K(2, created_at="2026-10-28T10:00:00+00:00"), K(3), K(4, account_type="funded"), K(5, firm="FTMO"), K(6, abo_gekuendigt_at="2026-11-20T00:00:00Z"),
          K(7, user_id=U2), K(8)]
PROFILE = [{"k1": {"archived": True, "reason": "blown"}, "k2": {"archived": True, "reason": "blown"}, "k3": {"archived": True, "reason": "passed"},
             "k4": {"archived": True, "reason": "blown"}, "k5": {"archived": True, "reason": "blown"}, "k6": {"archived": True, "reason": "blown"}},
           {"k7": {"archived": True, "reason": "blown"}},
           "kaputt", {"k1": "kein dict", "k2": {"archived": False, "reason": "blown", "at": "2026-11-30"}}]   # kaputte/ältere Einträge stören nie
archiv = ns["fk1_archiv_je_konto"](PROFILE, [a["id"] for a in konten])
check(archiv["k1"]["reason"] == "blown" and archiv["k2"]["archived"] is True and "k8" not in archiv, "Archiv über alle Profile: archiviert gewinnt, Nicht-dicts ignoriert")
z = f(konten, archiv, {"k1": date(2026, 10, 30)}, H, {U1: "Julian", U2: "Mike"})
ids = [x["konto_id"] for x in z]
check(set(ids) == {"k1", "k2", "k7"}, f"nur geblowte FTMO-Futures-Challenges ohne Marke (nie bestanden/Funded/andere Firma/gekündigt/aktiv) → {ids}")
# Review FK1: ein Admin (Pascal) archiviert das Konto einer Kunden-ID → Eintrag in SEINEM Profil, Zeile trotzdem bei der Kunden-ID
arch2 = ns["fk1_archiv_je_konto"](PROFILE + [{"k8": {"archived": True, "reason": "blown", "at": "2026-11-24T10:00:00Z"}}], [a["id"] for a in konten])
z2 = f(konten, arch2, {}, H, {U1: "Julian"})
check(any(x["konto_id"] == "k8" and x["user_id"] == U1 for x in z2), "von einem Admin-Login archiviert (anderes Profil) → erscheint bei der Konto-ID")
k1 = next(x for x in z if x["konto_id"] == "k1")
check(k1["kauf"] == "2026-10-30" and k1["verlaengert_am"] == "2026-11-29" and k1["tage"] == 4 and k1["rot"] is False,
      "Kaufdatum aus der Kauf-Buchung, 4 Tage → noch nicht rot")
k2 = next(x for x in z if x["konto_id"] == "k2")
check(k2["kauf"] == "2026-10-28" and k2["verlaengert_am"] == "2026-11-27" and k2["tage"] == 2 and k2["rot"] is True,
      "ohne Kauf-Buchung: Anlegetag (Dubai), 2 Tage → rot")
check(ids[0] == "k2" and k1["person"] == "Julian" and k1["ende4"] == "0761" and k1["firma"] == "FTMO Futures", "sortiert nach Verlängerungstag, Person + …4")
check(next(x for x in z if x["konto_id"] == "k7")["user_id"] == U2, "Zeile gehört zur ID des Kontos (Mike), nicht zum Login")

r = SRC[SRC.index('@app.route("/konto/abo-kuendigen"'):SRC.index("# ══ PA1", SRC.index('@app.route("/konto/abo-kuendigen"'))]   # FK1 steht direkt vor PA1
fk1_block = SRC[SRC.index("# ══ FK1 "):SRC.index("# ══ PA1")]
check(SRC.index("# ══ FK1 ") < SRC.index("# ══ PA1") and "/konto-suche" not in fk1_block,
      "FK1-Block steht vor dem PA1-Block, nicht zwischen /konto-suche/nachfolger und KONTEN PRÜFEN (dort schneidet der PA1-Test)")
check('_konto_ziel_uid({"user_id": str(acc.get("user_id"))})' in r and '"abo_gekuendigt_at": "is.null"' in r and 'acc.get("firm") != FK1_FIRMA' in r,
      "POST: Gate eigene ID/Admin, nur FTMO Futures, Marke einmal (is.null)")
check('"sql_fehlt": True' in r and "_admin_konto_gate()" in r and '"account_type": "eq.challenge"' in r, "GET: ohne Spalte leer, alle=1 nur mit Admin-Gate, nur Challenges")
check('"kind": "eq.account_purchase"' in r and 'ZoneInfo("Asia/Dubai")' in r, "Kaufdatum aus account_purchase, heute nach Dubai")
check('_sb_all("user_settings", {"select": "value", "key": "eq.archive"})' in r and "fk1_archiv_je_konto(" in r, "Route liest das Archiv aller Profile")
check("add column if not exists abo_gekuendigt_at timestamptz" in SQL and "create table" not in SQL.lower(), "SQL: eine Spalte, keine neue Tabelle")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)

#!/usr/bin/env python3
"""Selbsttest AC3 (05.11.2026): _konto_archiv_eintragen schreibt mit updated_at-Wächter — schreibt ein Tab/anderer Lauf zwischen Lesen und Schreiben,
wird neu gelesen und nur der eigene Eintrag ergänzt; fremde Einträge gehen nie verloren. Ohne Netz (sb_select/sb_update/_sb_anfrage ersetzt).
Aufruf: python3 tools/selftest_archiv_waechter.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


class DB:
    def __init__(self, zeile, konflikte=0):
        self.zeile, self.konflikte, self.schreiben, self.lesen = zeile, konflikte, [], 0

    def select(self, t, p):
        if t == "user_settings":
            self.lesen += 1
            return [dict(self.zeile)] if self.zeile else []
        return []                                                         # mt5_links: kein Echo-Link

    def update(self, t, guard, body):
        self.schreiben.append(("PATCH", dict(guard), sorted(body["value"])))
        if self.konflikte > 0:                                             # dazwischen schreibt jemand anderes
            self.konflikte -= 1
            self.zeile = {"value": dict(self.zeile["value"], **{"tab-1": {"archived": True, "reason": "hand"}}), "updated_at": "T2"}
            return []
        if guard.get("updated_at") != f"eq.{self.zeile['updated_at']}":
            return []
        self.zeile = {"value": body["value"], "updated_at": body["updated_at"]}
        return [{"user_id": "u"}]

    def anfrage(self, m, url, **kw):
        class R:
            status_code = 201

            def raise_for_status(self):
                return None
        if "user_settings" in url and getattr(self, "post_409", False):
            # gleichzeitig angelegt (Tab legt die Zeile mit tab-1 an, AC3b): POST → 409, danach steht die Zeile da
            self.post_409 = False
            self.schreiben.append(("POST 409", None, sorted(kw["json"]["value"])))
            self.zeile = {"value": {"tab-1": {"archived": True, "reason": "hand"}}, "updated_at": "T5"}
            r = R(); r.status_code = 409
            return r
        if "user_settings" in url:
            self.schreiben.append(("POST", None, sorted(kw["json"]["value"])))
            self.zeile = {"value": kw["json"]["value"], "updated_at": kw["json"]["updated_at"]}
        return R()


def lauf(db, aid="neu-1"):
    app.sb_select, app.sb_update, app._sb_anfrage = db.select, db.update, db.anfrage
    return app._konto_archiv_eintragen("u", aid, "blown", "T9", "100k Test")


db = DB({"value": {"alt-1": {"archived": True}}, "updated_at": "T1"})
ok(lauf(db) is True and db.zeile["value"].keys() == {"alt-1", "neu-1"} and db.schreiben[0][1]["updated_at"] == "eq.T1",
   f"normal: mit Wächter updated_at=eq.T1 geschrieben {db.schreiben}")
db = DB({"value": {"alt-1": {"archived": True}}, "updated_at": "T1"}, konflikte=1)
ok(lauf(db) is True and set(db.zeile["value"]) == {"alt-1", "tab-1", "neu-1"} and db.lesen == 2,
   f"Konflikt: Tab schreibt dazwischen tab-1 → neu gelesen, tab-1 bleibt {sorted(db.zeile['value'])}")
db = DB(None)
ok(lauf(db) is True and db.schreiben[0][0] == "POST" and set(db.zeile["value"]) == {"neu-1"}, "keine Zeile → angelegt")
db = DB(None); db.post_409 = True
ok(lauf(db) is True and [w[0] for w in db.schreiben] == ["POST 409", "PATCH"] and set(db.zeile["value"]) == {"tab-1", "neu-1"}
   and db.schreiben[1][1]["updated_at"] == "eq.T5",
   f"keine Zeile, aber gleichzeitig angelegt (POST 409) → neu gelesen, mit Wächter ergänzt, tab-1 bleibt {db.schreiben}")
db = DB({"value": {"neu-1": {"archived": True, "reason": "passed_pending"}}, "updated_at": "T1"})
ok(lauf(db) is False and not db.schreiben, "schon archiviert → nichts geschrieben, False")
db = DB({"value": {"alt-1": {"archived": True}}, "updated_at": "T1"}, konflikte=5)
try:
    lauf(db); ok(False, "dauernder Konflikt muss werfen")
except RuntimeError:
    ok(len(db.schreiben) == 3, "dauernder Konflikt → nach 3 Versuchen Fehler (Aufrufer meldet), nie blind überschrieben")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)

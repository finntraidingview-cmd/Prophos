#!/usr/bin/env python3
"""Selbsttest: PLANER-RECHTE HT (30.10.2026, Finn ~08:30). Nur „Finn + Pascal" und „Pascal" (admin_voll) dürfen in den Planern ändern,
andere HT-IDs nur ansehen, Emins Gruppe unverändert, PC-Tab-Automatik nie gesperrt. Ohne Netz (Auth/Supabase ersetzt).
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_planer_rechte_ht.py"""
import os
import re
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


R = app.planer_schreib_recht
VOLL = frozenset({"fp", "pascal"})
print("1) Regel (rein)")
check(R(True, "x", None, VOLL), "Admin darf")
check(R(False, "fp", None, VOLL) and R(False, "pascal", None, VOLL), "Finn + Pascal und Pascal dürfen")
check(not R(False, "jacob", None, VOLL), "andere HT-ID: nur ansehen")
check(R(False, "emin", frozenset({"emin", "amir"}), VOLL), "Emins Gruppe: unverändert")
check(not R(False, None, None, VOLL) and not R(False, "fp", None, frozenset()), "ohne ID / leere Liste → gesperrt")

print("2) Gate mit nachgebauter Anmeldung")
WER = {"uid": "jacob", "admin": False, "fehler": False}
app._admin_auth = lambda: ((("finn@x", None) if WER["admin"] else
                            (app.request.environ.__setitem__("prophos.admin_uid", WER["uid"]) or (None, (app.jsonify({"error": "x"}), 403)))))
app._wd_login = lambda: (WER["uid"], None)
app.admin_sicht_lesen = lambda u: (None, False)
app.admin_voll_uids = lambda: (_ for _ in ()).throw(RuntimeError("weg")) if WER["fehler"] else VOLL
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "g-e", "verwalter_id": "emin"}], "mitglieder": [{"gruppe_id": "g-e", "user_id": "amir"}]}
with app.app.test_request_context("/admin/auto-plan/bestaetigen", method="POST"):
    for uid, soll in (("jacob", 403), ("pascal", None), ("fp", None), ("emin", None), ("amir", None)):
        WER["uid"] = uid
        e = app._planer_schreib_gate()
        code = None if e is None else e[1]
        check(code == soll, f"{uid}: {'darf' if soll is None else soll} ({code})")
    WER.update(uid="jacob", fehler=True)
    e = app._planer_schreib_gate()
    check(e is not None and e[1] in (403, 502), f"Liste nicht lesbar → gesperrt ({e and e[1]})")
    WER.update(fehler=False, uid="pascal")
    m, err = app._planer_admin_auth()
    check(err is None and m, "Pascal gilt in den Planer-Routen wie ein Admin (_planer_admin_auth)")
    WER["uid"] = "jacob"
    check(app._planer_admin_auth()[1] is not None, "Jacob nicht")

cl = app.app.test_client()
for uid, soll in (("jacob", False), ("pascal", True), ("amir", True)):
    WER["uid"] = uid
    d = cl.get("/admin/planer-rechte", headers={"sb-token": "x"}).get_json()
    check(d.get("ok") and d.get("schreiben") is soll, f"GET /admin/planer-rechte {uid} → schreiben {d.get('schreiben')}")

print("3) Quelltext: Riegel an allen Schreib-Routen, Automatik frei")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()


def rumpf(name):
    i = src.index(f"\ndef {name}(")
    return src[i:src.find("\n\n\n", i)]


for f in ("_ap_eingriff", "admin_auto_plan_hedge_freigabe", "admin_auto_plan_ausgleichen", "admin_auto_plan_ids", "admin_gruppen_plan",
          "admin_auto_plan_eingriff", "admin_auto_plan_ausgleich_einstellung", "admin_auto_plan", "admin_plan_anlegen", "_fdp_eingriff",
          "admin_funded_plan_planen", "admin_funded_plan_ids", "_fcp_eingriff", "admin_funded_cfd_plan_einstellung", "admin_funded_cfd_plan_planen",
          "admin_wd_plaene"):
    check("_planer_schreib_gate()" in rumpf(f), f"Riegel in {f}")
for f in ("admin_auto_plan_start_protokoll", "admin_auto_plan_waage_start"):
    try:
        check("_planer_schreib_gate()" not in rumpf(f), f"kein Riegel in {f} (PC-Tab beim Start)")
    except ValueError:
        pass
check(set(app.PLANER_WD_AUTOMATIK) == {"ende", "endlesung", "endlesung_stand", "balance", "balance_stand", "tab_neu_laden"},
      "wd-plaene: PC-Tab-Automatik (ende, endlesung, Stände, balance, tab_neu_laden) nie gesperrt")
check("trocken" in rumpf("admin_auto_plan").split("_planer_schreib_gate()")[0][-400:], "Probelauf (trocken) bleibt für alle offen")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)

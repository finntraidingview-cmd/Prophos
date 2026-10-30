#!/usr/bin/env python3
"""Selbsttest NOTIZ JE KONTO IN REVIEW (Finn 30.10.2026: „OK, warten auf KYC"). Ohne Netz: Auth und Supabase ersetzt.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_review_notiz.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import requests  # noqa: E402
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) Lesen: nur Konten, die der Login im Radar sieht")
N = {"k1": "warten auf KYC", "k2": "fremde Gruppe", "k3": "Trade in Überprüfen", "k4": None}
w = app.hand_review_notizen(N, [{"konto_id": "k1"}, {"konto_id": "k4"}], [{"master_account_id": "k3"}])
check(w == {"k1": "warten auf KYC", "k3": "Trade in Überprüfen"}, f"k2 nicht sichtbar, leere fallen raus ({w})")
check(app.hand_review_notizen({}, None, None) == {} and app.hand_review_notizen(None, [{"konto_id": "k1"}], []) == {}, "ohne Daten leer")
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("Spalte fehlt"))
check(app._review_notizen_lesen() == {}, "Lesefehler (Spalte fehlt) kostet nur die Notizen")

print("2) Schreiben über /admin/wd-plaene")
BES, ICH = "u-marc", "u-finn"
ST = {"upd": [], "fehler": None, "cache": 0}


def sel(t, p):
    return [{"user_id": BES}] if t == "accounts" else []


def upd(t, p, body):
    if ST["fehler"]:
        raise ST["fehler"]
    ST["upd"].append((t, dict(p), dict(body)))
    return [{"id": "x"}]


app.sb_select, app.sb_update = sel, upd
app._wd_login = lambda: (ICH, None)
app._planer_admin_auth = lambda: ("finn@x", None)
app._admin_nur_uid = lambda: None
app._admin_verwalter = lambda: False
cl = app.app.test_client()
KID = "aaaaaaaa-1111-2222-3333-444444444444"


def rufe(notiz):
    ST["upd"].clear()
    app._hand_cache["probe"] = (9e12, {})
    return cl.patch("/admin/wd-plaene?ansicht=admin", json={"aktion": "review_notiz", "account_id": KID, "notiz": notiz})


r = rufe("  OK, warten auf KYC  ")
d = r.get_json()
check(r.status_code == 200 and d.get("notiz") == "OK, warten auf KYC" and ST["upd"][0][2] == {"review_notiz": "OK, warten auf KYC"}, f"fremdes Konto im Admin-Login, getrimmt ({d})")
check(ST["upd"][0][0] == "accounts" and ST["upd"][0][1] == {"id": f"eq.{KID}"} and len(ST["upd"]) == 1, "schreibt genau dieses Konto, sonst nichts")
check(not app._hand_cache, "Handarbeit-Cache geleert")
rufe("")
check(ST["upd"][0][2] == {"review_notiz": None}, "leer löscht")
rufe("x" * 500)
check(len(ST["upd"][0][2]["review_notiz"]) == app.REVIEW_NOTIZ_MAX, "Länge gedeckelt")
check(cl.patch("/admin/wd-plaene", json={"aktion": "review_notiz", "account_id": "kurz"}).status_code == 400, "ohne Konto 400")


class Antw:
    text = 'column accounts.review_notiz does not exist'


e = requests.exceptions.HTTPError("400")
e.response = Antw()
ST["fehler"] = e
r = rufe("x")
check(r.status_code == 409 and "sql/2026-10-30_review_notiz.sql" in r.get_json()["error"], "Spalte fehlt → 409 mit SQL-Datei")
ST["fehler"] = RuntimeError("weg")
check(rufe("x").status_code == 502, "anderer Fehler → 502")
ST["fehler"] = None

print("3) Rechte")
check("review_notiz" in app.PLANER_WD_AUTOMATIK, "kein Planer-Schreibriegel: jede ID darf ihre eigene")
app._admin_nur_uid = lambda: ICH
r = rufe("x")
check(r.status_code == 403 and not ST["upd"], "Login ohne Admin an fremdem Konto → 403, nichts geschrieben")
app._admin_nur_uid = lambda: BES
check(rufe("x").status_code == 200, "Besitzer im eigenen Login darf")
app._admin_verwalter = lambda: True
app._admin_nur_uid = lambda: "u-emin"
app.g = type("G", (), {"admin_sicht": frozenset({"u-emin", "u-amir"})})()
r = rufe("x")
check(r.status_code == 403 and not ST["upd"], "Verwalter fremder Gruppe → 403, nichts geschrieben")

print("4) Keine Wirkung auf Logik")
src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()


def fn_src(name):
    a = src.index(f"def {name}(")
    b = src.find("\ndef ", a + 1)
    return src[a:b]


frei = [n for n in ("ap_planen", "gp_planen", "fdp_planen", "fcp_planen", "_wd_erledigt_upd", "hand_gruppen", "ap_kontowert_konto") if "review_notiz" in fn_src(n)]
check(not frei, f"Planer, Abhaken und Kontowert kennen die Spalte nicht ({frei or 'alle sauber'})")
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
check("bstNotizZelle(x.kid, x.uid)" in html and "(fehlt ? '' : bstNotizZelle" in html, "Notiz nur in Review-Zeilen, nicht in Tage sammeln")
check("review_notiz" not in html[html.index("function accountToRow("):html.index("function accountToRow(") + 6000], "Konto-Dialog überschreibt die Notiz nicht")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)

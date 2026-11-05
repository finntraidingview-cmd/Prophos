#!/usr/bin/env python3
"""Selbsttest NOTIZ JE KONTO IN REVIEW (Finn 30.10.2026: „OK, warten auf KYC"). Ohne Netz: Auth und Supabase ersetzt.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_review_notiz.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

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


print("1) Lesen nach Besitzer, unabhängig von den Radar-Zeilen")
Z = [{"id": "k1", "user_id": "ht1", "review_notiz": "warten auf KYC"}, {"id": "k2", "user_id": "emin", "review_notiz": "Gruppe"},
     {"id": "k3", "user_id": "ht2", "review_notiz": "ohne Ziel-Tag"}, {"id": "k4", "user_id": "ht1", "review_notiz": None}]
check(app.hand_review_notizen(Z, None, {"emin"}) == {"k1": "warten auf KYC", "k3": "ohne Ziel-Tag"}, "ohne Einschränkung: alle außer ausgeblendet, leere fallen raus")
check(app.hand_review_notizen(Z, frozenset({"emin"}), {"ht1"}) == {"k2": "Gruppe"}, "Einschränkung gilt allein")
check(app.hand_review_notizen(None, None, None) == {} and app.hand_review_notizen(Z, frozenset(), None) == {}, "ohne Daten / leere Sicht: nichts")
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("Spalte fehlt"))
check(app._review_notizen_lesen() == [], "Lesefehler (Spalte fehlt) kostet nur die Notizen")

print("2) Echte Route, echte Sicht-Rechnung: nur Netz und Tabellen ersetzt")
app.SUPABASE_SERVICE_KEY = "x"
HT, HT2, FINN, EMIN, MITGL, MITGL2 = "u-ht", "u-ht2", "u-finn", "u-emin", "u-mitgl", "u-mitgl2"
BESITZ = {"konto-ht-1": HT, "konto-ht-2": HT2, "konto-emin": EMIN, "konto-mgl-1": MITGL, "konto-mgl-2": MITGL2}
NOTIZEN = [{"id": "konto-ht-1", "user_id": HT, "review_notiz": "HT ohne Ziel-Tag"}, {"id": "konto-emin", "user_id": EMIN, "review_notiz": "Emin intern"}, {"id": "konto-mgl-1", "user_id": MITGL, "review_notiz": "Mitglied"}]
ST = {"upd": [], "fehler": None}


class Antw:
    def __init__(self, d, code=200):
        self.d, self.status_code = d, code
        self.text = ""

    def json(self):
        return self.d


MAIL = {FINN: next(iter(app.ADMIN_EMAILS), "finn@x")}
app._auth_user_anfrage = lambda tok: Antw({"id": tok, "email": MAIL.get(tok, tok + "@x")})
app._auth_liste_anfrage = lambda: Antw({"users": [{"id": u, "email": MAIL.get(u, u + "@x"), "user_metadata": {"name": u}} for u in (HT, HT2, FINN, EMIN, MITGL, MITGL2)]})


def sel(t, p):
    # UNT0 (05.11.2026): eine ID ohne Zeile ist jetzt „ohne Unternehmen" (nur sich) — die Fixture bildet wie live HT als eigene Gruppe mit Zeilen ab
    if t == "id_gruppen":
        return [{"id": "g-h", "name": "Hermann Technologies", "verwalter_user_id": None}, {"id": "g-e", "name": "Emin", "verwalter_user_id": EMIN}]
    if t == "id_gruppe_mitglied":
        return [{"user_id": u, "gruppe_id": "g-h"} for u in (HT, HT2, FINN)] + [{"user_id": MITGL, "gruppe_id": "g-e"}, {"user_id": MITGL2, "gruppe_id": "g-e"}]
    if t == "accounts":
        b = BESITZ.get(str(p.get("id") or "").replace("eq.", ""))
        return [{"user_id": b}] if b else []
    return []


def upd(t, p, body):
    if ST["fehler"]:
        raise ST["fehler"]
    ST["upd"].append((t, dict(p), dict(body)))
    return [{"id": "x"}]


app.sb_select, app.sb_update = sel, upd
app._sb_all = lambda t, p: NOTIZEN if (t == "accounts" and "review_notiz" in str(p.get("select"))) else []
cl = app.app.test_client()


def rufe(wer, kid="konto-ht-1", notiz="x", admin=False):
    ST["upd"].clear()
    app._hand_cache["probe"] = (9e12, {})
    return cl.patch("/admin/wd-plaene" + ("?ansicht=admin" if admin else ""), json={"aktion": "review_notiz", "account_id": kid, "notiz": notiz}, headers={"sb-token": wer})


r = rufe(FINN, notiz="  OK, warten auf KYC  ", admin=True)
d = r.get_json()
check(r.status_code == 200 and d.get("notiz") == "OK, warten auf KYC" and ST["upd"][0][2] == {"review_notiz": "OK, warten auf KYC"}, f"Finn an fremdem HT-Konto, getrimmt ({d})")
check(ST["upd"][0][0] == "accounts" and ST["upd"][0][1] == {"id": "eq.konto-ht-1"} and len(ST["upd"]) == 1, "schreibt genau dieses Konto, sonst nichts")
check("probe" not in app._hand_cache, "Handarbeit-Cache geleert")
rufe(FINN, notiz="")
check(ST["upd"][0][2] == {"review_notiz": None}, "leer löscht")
rufe(FINN, notiz="x" * 500)
check(len(ST["upd"][0][2]["review_notiz"]) == app.REVIEW_NOTIZ_MAX, "Länge gedeckelt")
check(rufe(FINN, kid="kurz").status_code == 400, "ohne Konto 400")
check(rufe(FINN, kid="k-gibtsnicht").status_code == 404 and not ST["upd"], "unbekanntes Konto 404")

print("3) Rechte")
for wer, kid, adm, soll, name in (
        (HT, "konto-ht-1", False, 200, "HT-Login, eigenes Konto"),
        (HT, "konto-ht-2", False, 200, "HT-Login ohne admin_zugang, anderes HT-Konto"),
        (HT, "konto-emin", False, 403, "HT-Login an Konto des Verwalters"),
        (HT, "konto-mgl-1", False, 403, "HT-Login an Konto eines Mitglieds"),
        (FINN, "konto-emin", True, 403, "Finn an Konto der Verwalter-Gruppe"),
        (EMIN, "konto-mgl-1", True, 200, "Verwalter in der Admin-Ansicht, eigene Gruppe"),
        (EMIN, "konto-ht-1", True, 403, "Verwalter an HT-Konto"),
        (EMIN, "konto-mgl-1", False, 403, "Verwalter ohne Admin-Ansicht: nur eigene ID"),
        (MITGL, "konto-mgl-1", True, 200, "Mitglied, eigenes Konto"),
        (MITGL, "konto-mgl-2", True, 403, "Mitglied an Konto eines anderen Mitglieds"),
        (MITGL, "konto-ht-1", True, 403, "Mitglied an HT-Konto")):
    r = rufe(wer, kid=kid, admin=adm)
    check(r.status_code == soll and bool(ST["upd"]) == (soll == 200), f"{name} → {soll} ({r.status_code})")


class Fehlt:
    text = 'column accounts.review_notiz does not exist'


e = requests.exceptions.HTTPError("400")
e.response = Fehlt()
ST["fehler"] = e
r = rufe(FINN, admin=True)
check(r.status_code == 409 and "sql/2026-10-30_review_notiz.sql" in r.get_json()["error"], "Spalte fehlt → 409 mit SQL-Datei")
ST["fehler"] = RuntimeError("weg")
check(rufe(FINN, admin=True).status_code == 502, "anderer Fehler → 502")
ST["fehler"] = None


def hand(wer, admin=True):
    app._hand_cache.clear()
    r = cl.get("/admin/handarbeit" + ("?ansicht=admin" if admin else ""), headers={"sb-token": wer})
    return r.status_code, r.get_json() or {}


c, d = hand(HT, admin=False)
check(c == 200 and d.get("review_notizen") == {"konto-ht-1": "HT ohne Ziel-Tag"}, f"Login ohne Admin-E-Mail sieht HT-Notiz ohne Ziel-Tag, nicht die der Gruppe ({c}, {d.get('review_notizen')})")
check(EMIN in d.get("notiz_recht", {}).get("aus", []) and MITGL in d["notiz_recht"]["aus"], "HT-Login: Schreibrecht ohne Gruppe mit Verwalter")
c, d = hand(FINN)
check(d.get("review_notizen") == {"konto-ht-1": "HT ohne Ziel-Tag"}, f"Finn in der Standard-Sicht: keine Emin-Notiz ({d.get('review_notizen')})")
c, d = hand(MITGL)
check(d.get("review_notizen") == {"konto-emin": "Emin intern", "konto-mgl-1": "Mitglied"} and d.get("notiz_recht") == {"nur": [MITGL]}, f"Mitglied liest die Gruppe, schreibt nur sich ({d.get('notiz_recht')})")
c, d2 = hand(MITGL2)
check(d2.get("notiz_recht") == {"nur": [MITGL2]}, "Recht hängt am Login, nicht am Cache der Gruppe")
c, d3 = cl.get("/admin/handarbeit?ansicht=admin", headers={"sb-token": MITGL}).status_code, cl.get("/admin/handarbeit?ansicht=admin", headers={"sb-token": MITGL}).get_json()
check(d3.get("notiz_recht") == {"nur": [MITGL]}, "auch aus dem Cache: Recht des anfragenden Logins")
c, d = hand(EMIN)
check(d.get("notiz_recht", {}).get("nur") == sorted([EMIN, MITGL, MITGL2]), "Verwalter schreibt in seiner Gruppe")

print("3b) JS: $-Muster und Schreibrecht im echten Code")
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def fn(name):
    a = html.index("function " + name + "(")
    b = html.index("\n  }\n", a)
    return html[a:b + 4]


zeile = re.search(r"html: zeileDatum\(t\)(\.replace\(.*?'</div>'\)) \}\)\)", html).group(1)
probe = fn("bstNotizDarf") + fn("bstNotizZelle") + fn("bstNotizText") + r"""
const BST_NOTIZ_MAX = 120, _bstNotizNeu = new Map(), _bstNotizEdit = null
const escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const wdlUid = t => t.user_id
const _hand = { d: { review_notizen: { a: "$& und $' und $` und $1" }, notiz_recht: { aus: ['emin'] } } }
const t = { konto_id: 'a', user_id: 'u' }
const zeileDatum = () => '<div class="z">Zeile</div>'
const h = zeileDatum(t)""" + zeile + r"""
const r1 = { aus: ['emin'] }
_hand.d.notiz_recht = { nur: ['m1'] }
const nur = [bstNotizDarf('m1'), bstNotizDarf('m2')]
_hand.d.notiz_recht = { aus: ['emin'] }
const aus = [bstNotizDarf('ht'), bstNotizDarf('emin')]
_hand.d.notiz_recht = undefined
const ohne = bstNotizDarf('x')
_hand.d.notiz_recht = { nur: ['m1'] }
const fremdMit = bstNotizZelle('a', 'm2'), fremdLeer = bstNotizZelle('b', 'm2'), eigen = bstNotizZelle('b', 'm1')
print(JSON.stringify({ h, nur, aus, ohne, fremdMit, fremdLeer, eigen }))
"""
d0 = tempfile.mkdtemp()
pf = os.path.join(d0, "p.js")
open(pf, "w", encoding="utf-8").write(probe)
aus = subprocess.run([JSC, pf], capture_output=True, text=True, timeout=30)
w = json.loads(aus.stdout.strip()) if aus.returncode == 0 and aus.stdout.strip() else {}
check("$&amp; und $' und $` und $1" in w.get("h", "") and w.get("h", "").count('class="z"') == 1 and w.get("h", "").endswith("</span></div>"), f"$-Muster bleiben Text, Zeile bleibt ganz ({w.get('h', aus.stderr)[:160]})")
check(w.get("nur") == [True, False] and w.get("aus") == [True, False] and w.get("ohne") is True, "Schreibrecht: nur/aus, ohne Angabe prüft der Server")
check("data-wdl-bst-notiz" not in w.get("fremdMit", "x") and "ist-lesen" in w.get("fremdMit", "") and "Notiz" not in w.get("fremdLeer", "x") and "+ Notiz" in w.get("eigen", ""), "ohne Recht: Text nur lesbar, kein „+ Notiz“; mit Recht: Knopf")
check("keinFokus: true" in html and "_bstNotizEdit = { kid, uid, text, keinFokus: true }" in html, "Speicherfehler: Getipptes bleibt im Feld")

print("4) Keine Wirkung auf Logik")
src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()


def fn_src(name):
    a = src.index(f"def {name}(")
    b = src.find("\ndef ", a + 1)
    return src[a:b]


frei = [n for n in ("ap_planen", "gp_planen", "fdp_planen", "fcp_planen", "_wd_erledigt_upd", "hand_gruppen", "ap_kontowert_konto") if "review_notiz" in fn_src(n)]
check(not frei, f"Planer, Abhaken und Kontowert kennen die Spalte nicht ({frei or 'alle sauber'})")
check("bstNotizZelle(x.kid, x.uid)" in html and "(fehlt ? '' : bstNotizZelle" in html, "Notiz nur in Review-Zeilen, nicht in Tage sammeln")
check("review_notiz" not in html[html.index("function accountToRow("):html.index("function accountToRow(") + 6000], "Konto-Dialog überschreibt die Notiz nicht")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)

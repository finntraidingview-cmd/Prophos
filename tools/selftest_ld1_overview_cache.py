#!/usr/bin/env python3
"""Selbsttest LD1 (05.11.2026): Kurz-Cache von GET /admin/overview — je Login-ID + Parameter, frisch=1 baut neu, Fehler nie gemerkt,
gleichzeitige Anfragen bauen nur einmal (Single-Flight), Ablauf nach ADM_OV_CACHE_S. Ohne Netz (_wd_login, admin_build_overview ersetzt).
Aufruf: python3 tools/selftest_ld1_overview_cache.py"""
import os
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


ZUSTAND = {"uid": "uid-a", "baue": 0, "fehler": False, "dauer": 0.0}


def login():
    return ZUSTAND["uid"], None


def bauen(kapitel_id=None):
    ZUSTAND["baue"] += 1
    if ZUSTAND["dauer"]:
        time.sleep(ZUSTAND["dauer"])
    if ZUSTAND["fehler"]:
        raise RuntimeError("Supabase weg")
    return {"wer": ZUSTAND["uid"], "kap": kapitel_id, "n": ZUSTAND["baue"]}


app._wd_login = login
app.admin_build_overview = bauen
# Schreib-Route für den Test (vor dem ersten Request anlegen): erfolgreicher POST auf /admin/* leert den Cache (S4 05.11.2026)
app.app.add_url_rule("/admin/_ld1_test_schreiben", "ld1_test_schreiben", lambda: ("{}", 200), methods=["POST"])
app.app.add_url_rule("/admin/_ld1_test_fehler", "ld1_test_fehler", lambda: ("{}", 403), methods=["POST"])
c = app.app.test_client()


def holen(q=""):
    r = c.get("/admin/overview" + q)
    return r.status_code, r.get_json(), r.headers.get("X-Prophos-Cache")


def leeren():
    app._adm_ov_cache.clear()
    app._adm_ov_laeuft.clear()
    ZUSTAND.update(uid="uid-a", baue=0, fehler=False, dauer=0.0)


# 1) zweiter Aufruf derselben ID + Parameter = Treffer, Inhalt gleich
leeren()
s1, d1, a1 = holen("?ansicht=admin")
s2, d2, a2 = holen("?ansicht=admin")
ok(s1 == 200 and a1 == "miss" and a2 == "hit" and d1 == d2 and ZUSTAND["baue"] == 1, f"gleiche ID + Parameter: miss → hit, 1 Bau ({a1}/{a2}, {ZUSTAND['baue']})")

# 2) andere ID sieht nie den Stand der ersten
ZUSTAND["uid"] = "uid-b"
s3, d3, a3 = holen("?ansicht=admin")
ok(a3 == "miss" and d3["wer"] == "uid-b", f"andere ID: eigener Bau, nie fremder Stand ({a3}, {d3.get('wer')})")

# 3) andere Parameter (Gruppe, Kapitel) = eigener Eintrag; Reihenfolge egal
ZUSTAND["uid"] = "uid-a"
_, d4, a4 = holen("?ansicht=admin&gruppe=emin")
_, d5, a5 = holen("?gruppe=emin&ansicht=admin")
_, d6, a6 = holen("?ansicht=admin&kapitel=2")
ok(a4 == "miss" and a5 == "hit" and a6 == "miss" and d6["kap"] == 2, f"Gruppe/Kapitel eigener Eintrag, Reihenfolge egal ({a4}/{a5}/{a6})")

# 4) frisch=1 baut neu und legt den neuen Stand ab
n0 = ZUSTAND["baue"]
_, d7, a7 = holen("?ansicht=admin&frisch=1")
_, d8, a8 = holen("?ansicht=admin")
ok(a7 == "miss" and ZUSTAND["baue"] == n0 + 1 and a8 == "hit" and d8["n"] == d7["n"], f"frisch=1 baut neu, danach Treffer mit dem neuen Stand ({a7}/{a8})")

# 5) Ablauf nach ADM_OV_CACHE_S
alt = app.ADM_OV_CACHE_S
app.ADM_OV_CACHE_S = 0.2
leeren()
holen("?x=1")
time.sleep(0.3)
_, _, a9 = holen("?x=1")
app.ADM_OV_CACHE_S = alt
ok(a9 == "miss" and ZUSTAND["baue"] == 2, f"nach Ablauf neu gebaut ({a9})")

# 6) Fehler werden nie gemerkt
leeren()
ZUSTAND["fehler"] = True
s10, d10, _ = holen("?y=1")
ZUSTAND["fehler"] = False
s11, d11, a11 = holen("?y=1")
ok(s10 == 500 and s11 == 200 and a11 == "miss" and not app._adm_ov_laeuft, f"Fehler 500 nicht gemerkt, nächster Aufruf baut ({s10}/{s11}/{a11})")

# 7) Single-Flight: 6 gleichzeitige Anfragen → 1 Bau
leeren()
ZUSTAND["dauer"] = 0.4
arten = []


def los():
    with app.app.test_client() as cc:
        arten.append(cc.get("/admin/overview?z=1").headers.get("X-Prophos-Cache"))


th = [threading.Thread(target=los) for _ in range(6)]
for t in th:
    t.start()
for t in th:
    t.join()
ok(ZUSTAND["baue"] == 1 and sorted(arten).count("miss") == 1 and len(arten) == 6, f"6 gleichzeitig → 1 Bau ({ZUSTAND['baue']}, {sorted(arten)})")

# 8) frisch wartet nie auf einen laufenden Bau und baut selbst
leeren()
ZUSTAND["dauer"] = 0.4
t1 = threading.Thread(target=lambda: app.app.test_client().get("/admin/overview?w=1"))
t1.start()
time.sleep(0.1)
t0 = time.time()
_, _, a12 = holen("?w=1&frisch=1")
t1.join()
ok(a12 == "miss" and ZUSTAND["baue"] == 2, f"frisch=1 baut parallel selbst ({a12}, {ZUSTAND['baue']} Bauten, {time.time() - t0:.2f} s)")

# 8b) älterer (nicht frischer) Bau, der NACH dem frisch=1-Bau fertig wird, überschreibt dessen Stand nicht (Review LD1)
leeren()
ZUSTAND["dauer"] = 0.5
t2 = threading.Thread(target=lambda: app.app.test_client().get("/admin/overview?v=1"))
t2.start()
time.sleep(0.1)
ZUSTAND["dauer"] = 0.0
_, d13, _ = holen("?v=1&frisch=1")
t2.join()
_, d14, a14 = holen("?v=1")
ok(a14 == "hit" and d14["n"] == d13["n"], f"alter Bau überschreibt den frischen nicht (Treffer n={d14['n']}, frisch n={d13['n']})")

# 8c) erfolgreicher POST auf /admin/* leert den Cache aller IDs; abgelehnter (403) nicht
leeren()
holen("?s=1")
ZUSTAND["uid"] = "uid-b"; holen("?s=1"); ZUSTAND["uid"] = "uid-a"
c.post("/admin/_ld1_test_fehler")
_, _, a15 = holen("?s=1")
c.post("/admin/_ld1_test_schreiben")
_, _, a16 = holen("?s=1")
ZUSTAND["uid"] = "uid-b"; _, _, a17 = holen("?s=1"); ZUSTAND["uid"] = "uid-a"
ok(a15 == "hit" and a16 == "miss" and a17 == "miss", f"Schreiben auf /admin/* leert den Cache aller IDs, 403 nicht ({a15}/{a16}/{a17})")

# 8d) ein Bau, der VOR einem Schreiben begann, wird nicht gemerkt
leeren()
ZUSTAND["dauer"] = 0.4
t3 = threading.Thread(target=lambda: app.app.test_client().get("/admin/overview?w=2"))
t3.start()
time.sleep(0.1)
c.post("/admin/_ld1_test_schreiben")
t3.join()
ZUSTAND["dauer"] = 0.0
_, _, a18 = holen("?w=2")
ok(a18 == "miss", f"Bau vor dem Schreiben nicht gemerkt ({a18})")

# 9) Deckel: höchstens 40 Einträge
leeren()
for i in range(55):
    holen(f"?i={i}")
ok(len(app._adm_ov_cache) <= 40, f"Deckel 40 Einträge ({len(app._adm_ov_cache)})")

# 10) Schlüssel ohne frisch, mehrfache Parameter erhalten
from werkzeug.datastructures import MultiDict  # noqa: E402
k1 = app.adm_ov_schluessel("u", MultiDict([("a", "1"), ("a", "2"), ("frisch", "1")]))
k2 = app.adm_ov_schluessel("u", MultiDict([("a", "2"), ("a", "1")]))
ok(k1 == k2 == ("u", (("a", "1"), ("a", "2"))), f"Schlüssel ohne frisch, mehrfache erhalten ({k1})")

print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)

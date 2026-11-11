#!/usr/bin/env python3
"""Selbsttest TW2 — Hand überstimmt den Pause-Tag des Handels-Würfels (Finn 11.11.2026 21:30 über den Master: „Wenn ein Konto per Würfel einen Pause-Tag hat,
soll es überstimmt werden, wenn ich es von Hand reinnehme").

Aufruf:  python3 tools/selftest_tw2_hand_ueberstimmt.py
Ohne Netz, Platzhalter-IDs. Lädt den TW1-Block und die TW2-Helfer aus app.py (exec mit Stubs) und prüft:
  Pause ohne Hand → kein Plan (Grund bleibt) · Pause + Hand-Marke → Plan (kein Grund) · nur dieses Konto, nur dieser Tag · nächster Tag neu gewürfelt ·
  Lesefehler der Marken → Pause bleibt · Merker 20 s, frisch liest neu · Tag-Grenzen · Route mit Planer-Gate + wd_hand_darf · alle Würfel-Stellen laufen über
  tw_pause_grund · Frontend: Knopf nur am Pause-Chip (JavaScriptCore), WD „heute wieder rein“ setzt die Marke vor dem Anlegen, PC-Tab-Rückfall liest sie."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = src.index("# ══ TW1 HANDELS-WÜRFEL")
j = src.index('@app.route("/admin/handel-wuerfel"', i)
i2 = src.index("# ══ TW2 HAND ÜBERSTIMMT DEN PAUSE-TAG")
j2 = src.index('@app.route("/admin/handel-wuerfel/hand"', i2)

ZEILEN = {"tw": [{"planer": p, "gruppe": "", "pct": 75} for p in ("challenge_cfd", "challenge_futures", "funded_cfd", "funded_futures", "winning_days")]}
MARKEN = {"rows": [], "wirf": False, "n": 0}


def _sb_select(tab, params):
    assert tab == "planer_handel_wuerfel"
    return list(ZEILEN["tw"])


def _sb_all(tab, params):
    assert tab == "user_settings" and params.get("select") == "key"
    MARKEN["n"] += 1
    if MARKEN["wirf"]:
        raise RuntimeError("weg")
    muster = str(params.get("key") or "")
    assert muster.startswith("like.tw\\_hand:") and muster.endswith(":*"), muster   # „_“ escaped (Prüfer KANN 8)
    vor = muster[len("like."):-1].replace("\\_", "_")
    return [r for r in MARKEN["rows"] if str(r["key"]).startswith(vor)]


def _wd_num(v):
    try:
        return None if v is None or v == "" or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


KTX = {"ok": True, "gid_von": {}}
a = {"hashlib": hashlib, "time": time, "threading": threading, "_wd_num": _wd_num, "sb_select": _sb_select, "_sb_all": _sb_all,
     "ap_unt_kontext": lambda frisch=False: KTX, "print": lambda *x, **k: None, "datetime": __import__("datetime").datetime,
     "ap_regel_finden": lambda firmen, firm: next((f for f in firmen if firm in f.get("namen", [])), None),
     "ap_klasse": lambda route=None, firma=None: "futures" if str(route or "").startswith("tv") else "cfd"}
exec(src[i:j], a)
exec(src[i2:j2], a)
PG, KEY, HK, TAGOK = a["tw_pause_grund"], a["tw_hand_key"], a["tw_hand_konten"], a["tw_hand_tag_ok"]
HT = "00000000-0000-0000-0000-0000000000b1"
T1, T2 = "2026-11-12", "2026-11-13"


def konto(x):
    return f"00000000-0000-0000-0000-{x:012d}"


def setze(*paare):
    MARKEN["rows"] = [{"key": KEY(t, k)} for t, k in paare]
    a["_tw_hand"].clear()


print("1) Pause + Hand")
# ein Konto, das an T1 UND T2 Pause hat (Challenge CFD), und eins mit Pause an T1, Handelstag an T2
beide = next(konto(x) for x in range(5000) if PG("challenge_cfd", {"id": konto(x), "user_id": HT}, T1) and PG("challenge_cfd", {"id": konto(x), "user_id": HT}, T2))
nur1 = next(konto(x) for x in range(5000) if PG("challenge_cfd", {"id": konto(x), "user_id": HT}, T1) and not PG("challenge_cfd", {"id": konto(x), "user_id": HT}, T2))
anderes = next(konto(x) for x in range(5000, 9000) if PG("challenge_cfd", {"id": konto(x), "user_id": HT}, T1))
setze()
g0 = PG("challenge_cfd", {"id": beide, "user_id": HT}, T1)
check(bool(g0) and g0.startswith("Pause-Tag (Handels-Würfel 75 %)"), "Pause ohne Hand → Grund bleibt (kein Plan)")
setze((T1, beide))
check(PG("challenge_cfd", {"id": beide, "user_id": HT}, T1) is None, "Pause + Hand-Marke am selben Tag → kein Grund (Plan)")
check(bool(PG("challenge_cfd", {"id": anderes, "user_id": HT}, T1)), "Marke gilt nur für dieses Konto — ein anderes Pause-Konto bleibt draußen")
check(bool(PG("challenge_cfd", {"id": beide, "user_id": HT}, T2)), "nächster Tag: Marke von gestern gilt nicht, neu gewürfelt (Pause bleibt Pause)")
check(PG("challenge_cfd", {"id": nur1, "user_id": HT}, T2) is None, "nächster Tag neu gewürfelt: Pause-Konto von T1 handelt an T2 ohne Marke")
for pl in ("challenge_futures", "funded_cfd", "funded_futures", "winning_days"):
    setze()
    kp = next(konto(x) for x in range(5000) if PG(pl, {"id": konto(x), "user_id": HT}, T1))
    vorher = PG(pl, {"id": kp, "user_id": HT}, T1)
    setze((T1, kp))
    check(bool(vorher) and PG(pl, {"id": kp, "user_id": HT}, T1) is None, f"{pl}: Pause → mit Hand-Marke geplant")
setze((T1, beide))
gid_emin = "00000000-0000-0000-0000-0000000000a1"
KTX.update(gid_von={HT: gid_emin})
check(PG("challenge_cfd", {"id": beide, "user_id": HT}, T1) is None, "Unternehmen ohne eigenen Wert (100 %): kein Pause-Tag, Marke ändert nichts")
KTX.update(gid_von={})

print("2) Lesen der Marken")
setze((T1, beide))
MARKEN["n"] = 0
HK(T1); HK(T1); HK(T1)
check(MARKEN["n"] == 1, "Marken je Tag 20 s gemerkt (ein Lesen für viele Konten)")
HK(T1, frisch=True)
check(MARKEN["n"] == 2, "frisch=True liest neu (POST leert den Merker)")
setze((T1, beide))
MARKEN["wirf"] = True
check(bool(PG("challenge_cfd", {"id": beide, "user_id": HT}, T1)), "Marken nicht lesbar → Pause bleibt (wie TW1, fail-safe Richtung Würfel)")
MARKEN["wirf"] = False
a["_tw_hand"].clear()
check(PG("challenge_cfd", {"id": beide, "user_id": HT}, T1) is None, "nach dem Fehler wieder lesbar → Marke greift")
check(a["tw_hand_aus_zeilen"]([{"key": KEY(T1, "k1")}, {"key": KEY(T2, "k2")}, {"key": "tw_hand:" + T1 + ":"}, {"key": "anderes"}, None], T1) == {"k1"},
      "tw_hand_aus_zeilen: nur Marken genau dieses Tages, leere/fremde Schlüssel ignoriert")
check(KEY("2026-11-12T03:00:00Z", "k") == "tw_hand:2026-11-12:k", "Schlüssel tw_hand:<Tag>:<Konto>, Tag auf 10 Zeichen")
check(TAGOK("2026-11-12", "2026-11-12") and TAGOK("2026-11-11", "2026-11-12") and TAGOK("2026-11-14", "2026-11-12")
      and not TAGOK("2026-11-10", "2026-11-12") and not TAGOK("2026-11-15", "2026-11-12") and not TAGOK("12.11.2026", "2026-11-12")
      and not TAGOK("", "2026-11-12"), "Tag-Grenzen: gestern bis übermorgen, nur YYYY-MM-DD")

TPD = a["tw_pause_dazu"]
haupt = {"tag": T1, "ausgelassen": [{"konto_id": "k1", "grund": "Pause-Tag (Handels-Würfel 75 %) — heute kein Trade"}, {"konto_id": "k2", "grund": "Tagesdeckel der Firma"},
                                    {"konto_id": "k3", "grund": "Pause-Tag (Handels-Würfel 75 %)"}, {"konto_id": "k4", "grund": "Pause-Tag (Handels-Würfel 75 %)"}]}
nach = {"tag": T1, "quelle_lauf": "nachplanen", "nur_konten": ["k3"], "geplant": [{"konto_id": "k4"}], "ausgelassen": []}
z = TPD(nach, haupt)
check([x["konto_id"] for x in z["ausgelassen"]] == ["k1"], "Nachplan-Lauf: Pause-Zeilen des Haupt-Laufs dazu (nicht: andere Gründe, eigene nur_konten, schon geplant)")
check(TPD(dict(nach, quelle_lauf="nacht"), haupt) == dict(nach, quelle_lauf="nacht") and TPD(nach, dict(haupt, tag=T2)) == nach,
      "nur bei Nachplan-Lauf und nur derselbe Tag")
check('quelle="neq.nachplanen"' in src and "tw_pause_dazu(dict(erg" in src, "GET /admin/auto-plan mischt die Pause-Zeilen zum Nachplan-Lauf (HT-Weg)")

print("3) Route + Würfel-Stellen (Anker)")
route = src[j2:src.index("# ══ RV1 RANGE-WÜRFEL", j2)]
check("_planer_schreib_gate()" in route and "wd_hand_darf(" in route and "_wd_login()" in route, "Route: Planer-Gate + wd_hand_darf (eigene / Gruppe / HT-Admin)")
check('"user_id": str(acc["user_id"])' in route and "on_conflict" in route and "tw_hand_key(tag, kid)" in route,
      "Marke in user_settings des Konto-Besitzers (Upsert user_id,key)")
check("_tw_hand.pop(tag, None)" in route and "tw_hand_konten(tag, frisch=True)" in route, "Schreiben leert den Merker des Tages (nächster Lauf sieht die Marke sofort)")
check("rein = body.get(\"rein\", True) is not False" in route and '"DELETE"' in route, "rein false = Marke weg (Wurf gilt wieder)")
check(src.count("tw_pause_grund(") == 7 and src.count("tw_handelt(") == 2, "Würfel nur über tw_pause_grund (+ Definition/Test-Wurf), kein zweiter Weg")
for anker, name in (('tw_pause_grund("winning_days", acc[0]', "WD-POST"), ("_tw_g = tw_pause_grund(_tw_p, k[\"a\"], tag", "Challenge-Planer"),
                    ('tw_pause_grund("funded_futures", a, cme_heute', "Funded Futures"), ('tw_pause_grund("funded_cfd", a, plan_tag', "Funded CFD"),
                    ("if not (a and tw_pause_grund(pl, a, tag, w, k))", "Nachplan-Filter")):
    check(anker in src, f"{name} würfelt über tw_pause_grund (Marke greift dort)")
tpg = src[src.index("def tw_pause_grund("):src.index("def _tw_pct_txt(")]
check(tpg.index("tw_handelt(") < tpg.index("tw_hand_konten(tag)"), "Marken nur gelesen, wenn der Wurf Pause sagt (kein Lesen für Handelskonten)")
check('"tw_hand_konten" in globals()' in tpg, "ältere Selftest-Lader ohne TW2 bleiben grün")
check(src.index("# ══ TW2 HAND") > src.index('@app.route("/admin/handel-wuerfel", methods'), "TW2-Block hinter der TW1-Route (TW1-Lader unverändert)")

print("4) Frontend")
check("const WD_HINWEIS_PAUSE = 'Pause-Tag (Handels-Würfel) – heute kein Trade, morgen neu gewürfelt'" in html
      and 'TW_GRUND_WD = "Pause-Tag (Handels-Würfel) – heute kein Trade, morgen neu gewürfelt"' in src, "Schlüssel-Text WD-Pause unverändert (app.py = prophos.html)")
wkh = html[html.index("async function wdKontoHeute("):html.index("function wdRichtungChip(")]
check(wkh.index("k.hinweis === WD_HINWEIS_PAUSE") < wkh.index("k.aktiv = !!(rein && k.ext && !k.archiviert)")
      and "'/handel-wuerfel/hand'" in wkh and "return wdSay(" in wkh[wkh.index("'/handel-wuerfel/hand'"):wkh.index("k.aktiv = !!(rein")],
      "WD „heute wieder rein“ auf Pause-Tag: Marke ZUERST, Fehler → nichts geändert")
hw = html[html.index("async function hwWdPause("):html.index("window._hw = {")]
check("hwHandMarke(acc, tag, uid)" in hw and "`tw_hand:${String(tag || '').slice(0, 10)}:${acc.id}`" in hw and ".eq('user_id', String(uid))" in hw,
      "PC-Tab-Rückfall (hwWdPause) liest die Marke des Besitzers, Schlüssel wie app.py")
check(hw.index("hwWurf('winning_days'") < hw.index("hwHandMarke(acc, tag, uid)"), "Rückfall liest die Marke nur bei Pause-Wurf")
kl = html[html.index("const tplKlick = e => {"):html.index("tplRoot?.addEventListener('click', tplKlick)")]
check(kl.index("[data-tw-hand]") < kl.index("[data-tpl-ab]") and "e.stopPropagation()" in kl[kl.index("[data-tw-hand]"):kl.index("[data-tpl-ab]")],
      "Klick „heute rein“ vor dem Auf-/Zuklappen der ID (stoppt die Weitergabe)")
check("'[data-gp]', '[data-tw-hand]'" in html,
      "Knopf in der Planer-Rechte-Liste (ausgegraut ohne Schreibrecht)")
check(html.count("${twHandKnopf(c)}") == 2 and "tag: a.plan_tag || (roh && roh.tag) })" in html, "Knopf in Konten-Abdeckung und Heute je ID, Chip trägt den Plan-Tag")
check(html.count("grund: x.grund || '', plan_tag: d.tag || null }))") == 2, "Funded CFD/Futures: Zeile trägt den Plan-Tag des Planers (CME-Tag / plan_tag), nicht den Browser-Tag")
check(html.count("rein: true, sicht: 'admin' }") == 1 and "rein: rein !== false, sicht: 'admin' }" in html, "sicht admin mitgeschickt (Verwalter darf seine Gruppe)")
check(html.count("try{ window._apIdsRender?.() }catch(_){}") >= 2, "Admin-Reiter zeichnet nach dem Klick neu (window._apIdsRender)")

# twHandKnopf in JavaScriptCore
fn = html[html.index("  function twHandKnopf(c){"):html.index("  async function twHandRein(")]
js = """
const escapeHtml = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const _twHand = new Map();
""" + fn + """
const r = {};
r.pause = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel 75 %) — heute kein Trade, morgen neu gewürfelt' }, tag: '2026-11-12' });
r.anders = twHandKnopf({ r: { konto_id: 'k1', grund: 'Tagesdeckel der Firma' }, tag: '2026-11-12' });
r.wd = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel) – heute kein Trade, morgen neu gewürfelt' }, tag: '2026-11-12' });
r.ohneTag = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel 75 %)' } });
r.ohneKonto = twHandKnopf({ r: { grund: 'Pause-Tag (Handels-Würfel 75 %)' }, tag: '2026-11-12' });
_twHand.set('2026-11-12|k1', 'laeuft'); r.laeuft = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel 75 %)' }, tag: '2026-11-12' });
_twHand.set('2026-11-12|k1', 'ok'); r.ok = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel 75 %)' }, tag: '2026-11-12T01:00' });
_twHand.set('2026-11-12|k1', 'kaputt'); r.fehler = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag (Handels-Würfel 75 %)' }, tag: '2026-11-12' });
JSON.stringify(r);
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    r = json.loads(aus.stdout.strip() or "{}")
except Exception as e:
    r = {"_fehler": f"{type(e).__name__}: {e}"}
finally:
    os.unlink(f.name)
check('data-tw-hand="k1"' in r.get("pause", "") and 'data-tw-tag="2026-11-12"' in r.get("pause", "") and ">heute rein<" in r.get("pause", ""),
      "JS: Pause-Chip bekommt „heute rein“ mit Konto + Tag " + str(r.get("_fehler") or ""))
check(r.get("anders") == "" and r.get("ohneTag") == "" and r.get("ohneKonto") == "", "JS: kein Knopf bei anderem Grund, ohne Tag oder ohne Konto")
check(r.get("wd") == "", "JS: WD-Pause-Text bekommt hier keinen Knopf (WD hat „heute wieder rein“)")
check(" disabled" in r.get("laeuft", "") and "…" in r.get("laeuft", ""), "JS: während des Speicherns gesperrt")
check("✋ rein" in r.get("ok", "") and "<button" not in r.get("ok", ""), "JS: nach dem Speichern „✋ rein“ statt Knopf")
check("nicht gespeichert: kaputt" in r.get("fehler", "") and ">heute rein<" in r.get("fehler", ""), "JS: Fehler im Titel, Knopf wieder klickbar")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")

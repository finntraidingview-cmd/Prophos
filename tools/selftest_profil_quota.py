#!/usr/bin/env python3
"""Selbsttest PROFIL-BUCKET BEI VOLLEM SPEICHER (20.10.2026, Finn 15:50 Dubai: „ID-Wechsel gescheitert: … 'prophos_bucket_…' exceeded
the quota — was soll der Error? kann keine ID switchen" / „ich will IMMER ID wechseln können").
Aufruf:  python3 tools/selftest_profil_quota.py
Lädt den Profil-Block aus prophos.html (PROF_LS … profRestore) echt per osascript/JXA mit einem Fake-localStorage, der ab einer Grenze
QuotaExceededError wirft, und prüft: (1) Puffer-Klassifikation (prophos_cache_*, tpl_cache, wd_cache = Puffer; archive, kasse, kapitel …
= echt); (2) Wegsichern stufenweise — passt sofort / Puffer fremder Buckets / eigene Puffer / auch Puffer der Ziel-ID — echte Keys bleiben
in JEDEM Bucket; Hinweis für nach dem Neuladen ab Stufe 2 (seit IW1 12.11.2026: der eigene Bucket trägt nie Puffer, Stufen nur noch Rückfall); (3) passt der Bucket selbst ohne jeden Puffer nicht, fliegt der Fehler und kein
echter Key ist weg; (4) Einspielen: nur echte Keys (seit IW1 nie Puffer); (5) Deckel in tplCacheSchreiben/wdCacheSchreiben (Text).
Ohne Netz, Platzhalter-IDs."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


a = HTML.find("  const PROF_LS       = 'prophos_profiles'")
b = HTML.find("    } finally { _profBulkWrite = false }\n  }", a)
check(a > 0 and b > a, "Profil-Block gefunden (PROF_LS … profRestore)")
BLOCK = HTML[a:b + len("    } finally { _profBulkWrite = false }\n  }")]
check("const PROF_PUFFER_KEYS = ['prophos_tpl_cache', 'prophos_wd_cache']" in BLOCK and "function _profBucketSchreiben(userId, ziel, bucket)" in BLOCK,
      "PROF_PUFFER_KEYS + _profBucketSchreiben vorhanden")

VORSPANN = r"""
function FakeLS(limit){ this.m = new Map(); this.limit = limit }
FakeLS.prototype = {
  get length(){ return this.m.size },
  key(i){ const ks = [...this.m.keys()]; return i < ks.length ? ks[i] : null },
  getItem(k){ return this.m.has(k) ? this.m.get(k) : null },
  removeItem(k){ this.m.delete(k) },
  belegt(){ let t = 0; for(const [kk, vv] of this.m) t += kk.length + vv.length; return t },
  setItem(k, v){ v = String(v); let tot = k.length + v.length; for(const [kk, vv] of this.m) if(kk !== k) tot += kk.length + vv.length
    // wie im Browser: nur WACHSEN über die Grenze wirft, ein kleinerer Wert für einen vorhandenen Key passt immer
    if(tot > this.limit && tot > this.belegt()){ const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e } this.m.set(k, v) }
}
var localStorage = null, sessionStorage = { m: {}, setItem(k, v){ this.m[k] = String(v) }, getItem(k){ return k in this.m ? this.m[k] : null }, removeItem(k){ delete this.m[k] } }
var console = { warn(){}, log(){} }, atToast = null
// nachgezogen 11.11.2026 (ST1, Slave 2): 8972eb4d ID1c legt gewollt den Wechsel-Merker (zweiter Tab) in den Profil-Block — oberste Ebene braucht jetzt
// window (addEventListener, window.localStorage = der Fake), Storage.prototype (Sperre wickelt setItem/removeItem ein) und Takt-Stubs; JXA kennt sie nicht.
// Wegsichern/Einspielen selbst rufen den Merker nicht — die Prüfungen unten bleiben dieselben.
function Storage(){}
var window = { addEventListener(){}, get localStorage(){ return localStorage } }
var setInterval = () => 0, clearInterval = () => {}, document = { createElement(){ return { dataset: {} } }, body: { appendChild(){} } }, location = { reload(){} }
function fuellen(ls, keys){ for(const [k, v] of Object.entries(keys)) ls.m.set(k, v) }
const X = n => 'x'.repeat(n)
"""


def jxa(script):
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip()), ""
    except ValueError:
        return None, (r.stderr or r.stdout).strip()[:300]


if not shutil.which("osascript"):
    print("… osascript fehlt — nur Textprüfungen")
else:
    # (1) Klassifikation
    v, err = jxa(VORSPANN + BLOCK + """
JSON.stringify(['prophos_cache_plans','prophos_cache_accounts','prophos_tpl_cache','prophos_wd_cache','prophos_account_archive','prophos_kapitel','prophos_bulk_templates','prophos_tp_route','prophos_profiles'].map(profIstPuffer))""")
    check(v == [True, True, True, True, False, False, False, False, False], f"profIstPuffer: cache_*/tpl_cache/wd_cache = Puffer, archive/kapitel/bulk_templates/tp_route/profiles = echt ({v or err})")

    # (2) Wegsichern stufenweise. Fremde Buckets a/b/c (echt 5 KB, wahlweise + tpl_cache 60 KB + cache_plans 80 KB), Ziel-Bucket immer mit
    # Puffern (145 KB), aktuelle ID lose: echt 8 KB (+ Puffer tpl 90 / wd 40 / cache_plans 100 KB). Die Grenze = Bestand + delta — der Bestand
    # liegt immer darunter (wie im Browser), erst der neue Bucket der alten ID schiebt darüber; die losen Keys zählen dabei noch mit.
    SZENE = r"""
function szene(o){
  localStorage = new FakeLS(1e12)
  const bucket = (mitPuffer) => JSON.stringify(Object.assign({ prophos_account_archive: X(5000), prophos_kapitel: '{"id":2}' }, mitPuffer ? { prophos_tpl_cache: X(60000), prophos_cache_plans: X(80000) } : {}))
  fuellen(localStorage, Object.assign({ prophos_profiles: '[]', prophos_active_profile: 'me', prophos_bucket_a: bucket(o.fremdPuffer), prophos_bucket_b: bucket(o.fremdPuffer), prophos_bucket_c: bucket(o.fremdPuffer), prophos_bucket_ziel: bucket(true),
    prophos_account_archive: X(o.loseEcht || 8000), prophos_kapitel: '{"id":2}', 'prophos_kasse_frei:me': '1' }, o.losePuffer === false ? {} : { prophos_tpl_cache: X(90000), prophos_wd_cache: X(40000), prophos_cache_plans: X(100000) }))
  const belegt0 = localStorage.belegt()
  localStorage.limit = belegt0 + o.delta
  sessionStorage.m = {}
  let fehler = null
  try{ profSnapshotAndClear('me', 'ziel') }catch(e){ fehler = e.name }
  const B = k => { try{ return JSON.parse(localStorage.getItem('prophos_bucket_' + k) || 'null') }catch(_){ return null } }
  const keys = x => x ? Object.keys(x).sort() : null
  return { fehler, belegt0, me: keys(B('me')), a: keys(B('a')), ziel: keys(B('ziel')), hinweis: sessionStorage.getItem('prophos_profil_hinweis'),
    rest: [...localStorage.m.keys()].filter(k => !k.startsWith('prophos_bucket_')).sort(), echtMe: B('me') ? B('me').prophos_account_archive === X(o.loseEcht || 8000) && B('me')['prophos_kasse_frei:me'] === '1' : null,
    echtA: B('a') ? B('a').prophos_account_archive === X(5000) : null, echtZiel: B('ziel') ? B('ziel').prophos_account_archive === X(5000) : null }
}
"""
    ECHT = ["prophos_account_archive", "prophos_kapitel", "prophos_kasse_frei:me"]
    VOLL = sorted(ECHT + ["prophos_tpl_cache", "prophos_wd_cache", "prophos_cache_plans"])
    # nachgezogen IW1 (12.11.2026, Master-OK): profSnapshotAndClear legt KEINE Puffer mehr in den Bucket (nur echte Keys) — die Puffer der alten ID
    # werden nur geleert. Die Stufen von _profBucketSchreiben bleiben als Rückfall für alte Buckets mit Puffern und werden unten direkt geprüft.
    # Stufe 0: genug Platz → eigener Bucket nur echte Keys, fremde unberührt
    v, err = jxa(VORSPANN + BLOCK + SZENE + "JSON.stringify(szene({ fremdPuffer: true, delta: 300000 }))")
    check(bool(v) and v["fehler"] is None and v["me"] == ECHT and "prophos_tpl_cache" in v["a"] and v["hinweis"] is None, f"IW1: eigener Bucket ohne Puffer (nur echte Keys), fremde unberührt, kein Hinweis ({err or ''})")
    check(bool(v) and v["rest"] == ["prophos_active_profile", "prophos_profiles"], "nach dem Wegsichern liegen nur die System-Keys lose im localStorage (Puffer der alten ID geleert)")
    # früher Stufe 1/2: mit Puffern 238 KB, ohne nur 8 KB → passt jetzt sofort, nichts wird geworfen, kein Hinweis
    v, err = jxa(VORSPANN + BLOCK + SZENE + "JSON.stringify(szene({ fremdPuffer: true, delta: 100000 }))")
    check(bool(v) and v["fehler"] is None and v["me"] == ECHT and "prophos_tpl_cache" in v["a"] and v["hinweis"] is None and v["echtA"] is True and v["echtMe"] is True,
          f"IW1: wenig Platz — Bucket ohne Puffer passt sofort, fremde Buckets unangetastet, echte Keys unversehrt ({err or ''})")
    v, err = jxa(VORSPANN + BLOCK + SZENE + "JSON.stringify(szene({ fremdPuffer: false, delta: 100000 }))")
    check(bool(v) and v["fehler"] is None and v["me"] == ECHT and "prophos_tpl_cache" in (v["ziel"] or []) and v["echtMe"] is True and v["hinweis"] is None,
          f"IW1: ohne fremde Puffer — eigener Bucket echte Keys, Ziel-Bucket unangetastet, kein Hinweis ({err or ''})")
    # Stufe 3: auch 8 KB passen nicht mehr → die Puffer der Ziel-ID (140 KB) fliegen, dann geht der Wechsel durch
    v, err = jxa(VORSPANN + BLOCK + SZENE + "JSON.stringify(szene({ fremdPuffer: false, delta: 2000 }))")
    check(bool(v) and v["fehler"] is None and v["ziel"] == ["prophos_account_archive", "prophos_kapitel"] and v["me"] == ECHT and v["echtZiel"] is True and v["echtMe"] is True,
          f"Stufe 3: auch Ziel-Puffer verworfen, echte Keys überall da, Wechsel geht durch ({err or ''})")
    check(bool(v) and v["hinweis"] and "verworfen" in v["hinweis"], "Stufe 3: Hinweis gemerkt")
    # Rückfall-Stufen direkt an _profBucketSchreiben (Bucket MIT Puffern, wie ihn alte Stände geschrieben hätten)
    STUFEN = r"""
function stufe(o){
  localStorage = new FakeLS(1e12)
  const fb = JSON.stringify({ prophos_account_archive: X(5000), prophos_tpl_cache: X(60000), prophos_cache_plans: X(80000) })
  fuellen(localStorage, { prophos_bucket_a: o.fremd ? fb : JSON.stringify({ prophos_account_archive: X(5000) }), prophos_bucket_ziel: fb })
  localStorage.limit = localStorage.belegt() + o.delta
  const b = { prophos_account_archive: X(8000), prophos_tpl_cache: X(90000), prophos_cache_plans: X(100000) }
  const r = _profBucketSchreiben('me', 'ziel', b)
  const K = k => Object.keys(JSON.parse(localStorage.getItem('prophos_bucket_' + k))).sort()
  return { stufe: r.stufe, me: K('me'), a: K('a'), ziel: K('ziel') }
}
"""
    v, err = jxa(VORSPANN + BLOCK + STUFEN + "JSON.stringify([stufe({ fremd: true, delta: 100000 }), stufe({ fremd: false, delta: 100000 })])")
    check(bool(v) and v[0]["stufe"] == 1 and v[0]["a"] == ["prophos_account_archive"] and "prophos_tpl_cache" in v[0]["ziel"] and "prophos_tpl_cache" in v[0]["me"],
          f"Rückfall Stufe 1: Puffer fremder Buckets weg, Ziel geschont ({v or err})")
    check(bool(v) and v[1]["stufe"] == 2 and v[1]["me"] == ["prophos_account_archive"] and "prophos_tpl_cache" in v[1]["ziel"],
          f"Rückfall Stufe 2: eigene Puffer verworfen, Ziel geschont ({v or err})")
    # (3) unmöglich: nur echte Keys überall (eigene 300 KB), kein Puffer, der Platz schaffen könnte → Fehler fliegt, nichts Echtes verloren
    v, err = jxa(VORSPANN + BLOCK + SZENE + "JSON.stringify(szene({ fremdPuffer: false, losePuffer: false, loseEcht: 300000, delta: 1000 }))")
    check(bool(v) and v["fehler"] == "QuotaExceededError" and v["me"] is None and v["echtA"] is True and v["echtZiel"] is True and "prophos_account_archive" in v["rest"] and "prophos_kasse_frei:me" in v["rest"],
          f"ohne jeden Puffer zu groß: Fehler fliegt, echte Keys fremder IDs unversehrt, eigene bleiben lose im localStorage ({err or ''})")

    # (4) Einspielen: echte zuerst, Puffer nur wenn sie passen
    v, err = jxa(VORSPANN + BLOCK + r"""
localStorage = new FakeLS(300000); sessionStorage.m = {}   // belegt vorher 226 KB (zwei Buckets): echte 9 KB + tpl 50 KB passen, wd 30 KB und cache_plans 70 KB nicht mehr
fuellen(localStorage, { prophos_profiles: '[]', 'prophos_bucket_a': JSON.stringify({ prophos_account_archive: X(5000), prophos_cache_plans: X(60000) }),
  'prophos_bucket_ziel': JSON.stringify({ prophos_account_archive: X(9000), prophos_kapitel: '{"id":2}', prophos_tpl_cache: X(50000), prophos_wd_cache: X(30000), prophos_cache_plans: X(70000) }) })
profRestore('ziel')
JSON.stringify({ keys: [...localStorage.m.keys()].filter(k => !k.startsWith('prophos_bucket_') && k !== 'prophos_profiles').sort(), a: Object.keys(JSON.parse(localStorage.getItem('prophos_bucket_a'))), hinweis: sessionStorage.getItem('prophos_profil_hinweis'), bulk: _profBulkWrite })""")
    # nachgezogen IW1: Puffer werden nie eingespielt, der Ziel-Bucket verliert sie dabei; fremde Buckets bleiben, wie sie sind
    check(bool(v) and v["keys"] == ["prophos_account_archive", "prophos_kapitel"] and v["bulk"] is False and v["a"] == ["prophos_account_archive", "prophos_cache_plans"],
          f"IW1 Einspielen: nur echte Keys, kein Puffer (lädt frisch), fremder Bucket unberührt, Sync-Riegel wieder frei ({v or err})")
    check(bool(v) and v["hinweis"] is None, "IW1 Einspielen: kein Hinweis (kein Puffer übersprungen, sondern gewollt draußen)")
    v, err = jxa(VORSPANN + BLOCK + r"""
localStorage = new FakeLS(1e12); fuellen(localStorage, { 'prophos_bucket_ziel': JSON.stringify({ prophos_account_archive: X(9000), prophos_tpl_cache: X(50000), prophos_wd_cache: X(30000) }) })
profRestore('ziel'); JSON.stringify(Object.keys(JSON.parse(localStorage.getItem('prophos_bucket_ziel'))))""")
    check(v == ["prophos_account_archive"], f"IW1 Einspielen: Ziel-Bucket danach ohne Puffer ({v or err})")

# (5) Deckel + Haken (Text)
check("const TPL_CACHE_MAX_KB = 250" in HTML and "if(s.length > TPL_CACHE_MAX_KB * 1024){ c.lt = []; s = JSON.stringify(c) }" in HTML and "c.bilanz = []" in HTML,
      "tplCacheSchreiben: Deckel 250 KB — erst ohne Live-Zeilen, dann ohne Bilanz")
check("const WD_CACHE_MAX_KB = 200" in HTML and "if(s.length > WD_CACHE_MAX_KB * 1024){ c.konten = []; s = JSON.stringify(c) }" in HTML and "c.rows = []" in HTML,
      "wdCacheSchreiben: Deckel 200 KB — erst ohne Konten, dann ohne Zeilen")
check("try{ profHinweisZeigen() }catch(_){}" in HTML, "Hinweis wird nach dem Neuladen gezeigt (hydrateFromCache)")
check("const echte  = eintraege.filter(([k]) => !profIstPuffer(k))" in HTML, "profRestore nutzt dieselbe Puffer-Definition")
check("for(const k of keys) if(!profIstPuffer(k)) bucket[k] = localStorage.getItem(k)" in HTML, "IW1: profSnapshotAndClear legt keine Puffer in den Bucket")
check(HTML.count("k.startsWith(PROF_CACHE)") == 1 and HTML.count("c.startsWith(PROF_CACHE)") == 0, "prophos_cache_-Vergleich nur noch in profIstPuffer, nirgends sonst")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")

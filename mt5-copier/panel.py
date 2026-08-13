#!/usr/bin/env python3
"""
Prophos Copier-Panel — kleines Web-Frontend für die lokalen MT5-Copier auf DIESEM PC.

Zweck: Multiplikator, Symbol-Mapping, max_lots und Modus im Browser setzen statt in der
Textdatei — für mehrere Prop-Firmen/Accounts gleichzeitig. Zeigt außerdem live, was jeder
Copier gerade macht (Konten, offene Hedges, Log).

Bewusst eigenständig: Prophos (app.py / prophos.html) wird NICHT angefasst.

Technik:
  · Nur Python-Standardbibliothek — kein pip install, keine Cloud, keine Schlüssel.
  · Bindet ausschließlich an 127.0.0.1 — aus dem Netz nicht erreichbar.
  · Mehrere Instanzen: jede `config*.json` im Ordner ist eine Instanz
    (config.json, config-ftmo.json, config-apex.json …). Der Copier für eine bestimmte
    Config wird per Umgebungsvariable gestartet:  set COPIER_CONFIG=config-ftmo.json
    Der Status landet automatisch in der passenden `status*.json`.

Start:  python panel.py     →  http://127.0.0.1:8770
"""

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PANEL_PORT", "8770"))

# Nur diese Felder darf das Panel schreiben. Terminal-Pfade und die erwarteten
# Kontonummern bleiben tabu — das sind die Sicherheitsanker des Copiers.
WRITABLE = {"multiplier", "symbol_map", "max_lots_per_hedge", "mode"}
MODES = ("dryrun", "demo", "live")


def instances():
    """Alle config*.json im Ordner -> [{name, config_file, status_file}]"""
    out = []
    for fn in sorted(os.listdir(HERE)):
        if not re.fullmatch(r"config.*\.json", fn) or fn.endswith(".tmp"):
            continue
        if fn in ("config.example.json", "config.fusion-test.json"):
            continue
        name = fn[len("config"):-len(".json")].lstrip("-_") or "standard"
        out.append({"name": name, "config_file": fn,
                    "status_file": fn.replace("config", "status", 1)})
    return out


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot():
    data = []
    for inst in instances():
        cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        data.append({
            "name": inst["name"],
            "config_file": inst["config_file"],
            "mode": cfg.get("mode"),
            "multiplier": cfg.get("multiplier"),
            "max_lots": cfg.get("max_lots_per_hedge"),
            "symbol_map": cfg.get("symbol_map") or {},
            "master_expected": cfg.get("master_expected_login"),
            "hedge_expected": cfg.get("hedge_expected_login"),
            "status": st,
            "age": age,
            # "lebt" = Statusdatei ist frisch. Der Copier schreibt alle ~3s.
            "alive": bool(st.get("running")) and age is not None and age <= 15,
        })
    return data


def patch_config(fname, patch):
    """Nur erlaubte Felder schreiben, Datei atomar ersetzen."""
    path = os.path.join(HERE, fname)
    cfg = read_json(path)
    if cfg is None:
        return False, f"{fname} nicht lesbar"
    changed = []
    for k, v in patch.items():
        if k not in WRITABLE:
            continue
        if k == "mode":
            v = str(v).lower()
            if v not in MODES:
                return False, f"Modus '{v}' ungueltig"
        if k in ("multiplier", "max_lots_per_hedge"):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: '{v}' ist keine Zahl"
            if v <= 0:
                return False, f"{k} muss groesser als 0 sein"
        if k == "symbol_map":
            if not isinstance(v, dict) or not all(isinstance(a, str) and isinstance(b, str) for a, b in v.items()):
                return False, "symbol_map muss Text→Text sein"
        if cfg.get(k) != v:
            cfg[k] = v
            changed.append(k)
    if not changed:
        return True, "keine Aenderung"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return True, "gespeichert: " + ", ".join(changed)


PAGE = """<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Copier-Panel</title><style>
*{box-sizing:border-box}
body{margin:0;background:#12141a;color:#e7e9ee;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:14px 20px;border-bottom:1px solid #262a33;display:flex;align-items:center;gap:12px}
h1{font-size:16px;font-weight:600;margin:0}
.sub{color:#8b93a3;font-size:12px}
main{padding:18px 20px;display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(430px,1fr))}
.card{background:#181b22;border:1px solid #262a33;border-radius:12px;padding:16px}
.top{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.name{font-weight:600;font-size:15px}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid}
.b-dry{color:#8b93a3;border-color:#3a4150}
.b-demo{color:#7fd4a8;border-color:#2b5f45;background:#14251d}
.b-live{color:#ffb3a7;border-color:#6b3630;background:#251715}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
.on{background:#3fbf7f}.off{background:#c2544a}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:12.5px;color:#aeb6c4;margin-bottom:12px}
.kv b{color:#e7e9ee;font-weight:500;font-variant-numeric:tabular-nums}
label{display:block;font-size:11px;color:#8b93a3;margin:10px 0 4px}
input,select{width:100%;background:#0e1015;border:1px solid #2c313c;color:#e7e9ee;border-radius:7px;padding:7px 9px;font:13px inherit}
input:focus,select:focus{outline:0;border-color:#5b6ef0}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.map{display:grid;grid-template-columns:1fr auto 1fr auto;gap:6px;align-items:center;margin-top:5px}
.map span{color:#6d7484;font-size:12px}
.x{background:none;border:0;color:#7a818f;cursor:pointer;font-size:15px;padding:0 4px}
button{background:#5b6ef0;border:0;color:#fff;border-radius:7px;padding:8px 14px;font:600 13px inherit;cursor:pointer}
button.ghost{background:#20242d;color:#c3c9d6}
.acts{display:flex;gap:8px;margin-top:14px;align-items:center}
.msg{font-size:12px;color:#7fd4a8;min-height:16px;flex:1}
.msg.err{color:#ffb3a7}
pre{background:#0e1015;border:1px solid #22262f;border-radius:8px;padding:9px;margin:10px 0 0;font-size:11.5px;
    max-height:150px;overflow:auto;color:#9fa7b6;white-space:pre-wrap}
.warn{background:#251715;border:1px solid #6b3630;color:#ffb3a7;padding:8px 10px;border-radius:8px;font-size:12px;margin-top:10px}
.empty{color:#8b93a3;padding:30px 20px}
</style></head><body>
<header><h1>Copier-Panel</h1><span class=sub id=hint>lokal auf diesem PC · Prophos bleibt unangetastet</span></header>
<main id=app><div class=empty>lade…</div></main>
<script>
const state={};
function badge(m){const c=m==='live'?'b-live':m==='demo'?'b-demo':'b-dry';return `<span class="badge ${c}">${(m||'?').toUpperCase()}</span>`}
function mapRows(name,map){
  const e=Object.entries(map);
  return e.map(([k,v],i)=>`<div class=map>
    <input value="${k}" data-mk="${name}" data-i="${i}" placeholder="Master-Symbol">
    <span>→</span>
    <input value="${v}" data-mv="${name}" data-i="${i}" placeholder="Hedge-Symbol">
    <button class=x data-del="${name}" data-i="${i}" title="Zeile entfernen">×</button></div>`).join('')
   +`<div class=map><input data-mk="${name}" data-i="${e.length}" placeholder="neues Master-Symbol">
     <span>→</span><input data-mv="${name}" data-i="${e.length}" placeholder="Hedge-Symbol"><span></span></div>`;
}
function card(d){
  const s=d.status||{}, live=d.alive;
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  return `<div class=card data-name="${d.name}">
   <div class=top><span class=name>${d.name}</span>${badge(d.mode)}
     <span class=sub style="margin-left:auto"><span class="dot ${live?'on':'off'}"></span>${live?'läuft':'gestoppt'}${d.age!=null?` · ${d.age}s`:''}</span></div>
   <div class=kv>
     <span>Master</span><b>${s.master_login||d.master_expected||'—'}</b>
     <span>Hedge</span><b>${s.hedge_login||d.hedge_expected||'—'}</b>
     <span>Master-Positionen</span><b>${pos}</b>
     <span>offene Hedges</span><b>${hed}</b>
   </div>
   ${s.note?`<div class=warn>${s.note}</div>`:''}
   ${(s.blocked||[]).length?`<div class=warn>Gestoppt für Master-Pos: ${(s.blocked||[]).join(', ')} — im Hedge-Terminal prüfen</div>`:''}
   <div class=row>
     <div><label>Multiplikator</label><input type=number step=0.001 min=0 value="${d.multiplier??''}" data-f=multiplier data-n="${d.name}"></div>
     <div><label>max Lots pro Hedge</label><input type=number step=0.01 min=0 value="${d.max_lots??''}" data-f=max_lots_per_hedge data-n="${d.name}"></div>
   </div>
   <label>Modus</label>
   <select data-f=mode data-n="${d.name}">
     <option value=dryrun ${d.mode==='dryrun'?'selected':''}>dryrun — nur mitlesen, keine Order</option>
     <option value=demo ${d.mode==='demo'?'selected':''}>demo — echte Order, nur Demo-Konto</option>
     <option value=live ${d.mode==='live'?'selected':''}>live — echtes Geld</option>
   </select>
   <label>Symbol-Mapping (Master → Hedge)</label>
   <div data-maps="${d.name}">${mapRows(d.name,d.symbol_map||{})}</div>
   <div class=acts><button data-save="${d.name}">Speichern &amp; pushen</button>
     <span class="msg" id="m-${d.name}"></span></div>
   <pre>${(s.log||[]).slice(-14).join('\\n')||'noch keine Log-Zeilen'}</pre>
  </div>`;
}
async function load(){
  const r=await fetch('/api/instances'); const d=await r.json();
  if(!d.length){document.getElementById('app').innerHTML='<div class=empty>Keine <code>config*.json</code> gefunden. Lege eine config.json im Copier-Ordner an.</div>';return}
  const focus=document.activeElement, keep=focus&&focus.tagName==='INPUT'?focus.getAttribute('data-f')||focus.getAttribute('data-mk')||focus.getAttribute('data-mv'):null;
  if(!keep) document.getElementById('app').innerHTML=d.map(card).join('');
  d.forEach(x=>state[x.name]=x);
}
document.addEventListener('click',async e=>{
  const del=e.target.getAttribute&&e.target.getAttribute('data-del');
  if(del){const i=+e.target.getAttribute('data-i');const m=state[del].symbol_map;const k=Object.keys(m)[i];delete m[k];
    document.querySelector(`[data-maps="${del}"]`).innerHTML=mapRows(del,m);return}
  const name=e.target.getAttribute&&e.target.getAttribute('data-save'); if(!name)return;
  const card=document.querySelector(`.card[data-name="${name}"]`);
  const patch={};
  card.querySelectorAll('[data-f]').forEach(el=>patch[el.getAttribute('data-f')]=el.value);
  const map={};
  const ks=[...card.querySelectorAll('[data-mk]')], vs=[...card.querySelectorAll('[data-mv]')];
  ks.forEach((k,i)=>{const a=k.value.trim(), b=(vs[i]||{}).value?.trim(); if(a&&b) map[a]=b});
  patch.symbol_map=map;
  const msg=document.getElementById('m-'+name); msg.className='msg'; msg.textContent='speichere…';
  const r=await fetch('/api/save?name='+encodeURIComponent(name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const d=await r.json();
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?(d.msg+' — der Copier übernimmt es in ~2s'+(d.restart?' (Modus: Neustart läuft automatisch)':'')):('Fehler: '+d.msg);
  setTimeout(load,2500);
});
load(); setInterval(load,3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/instances":
            return self._send(200, json.dumps(snapshot(), ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/save":
            return self._send(404, json.dumps({"error": "not found"}))
        name = (parse_qs(u.query).get("name") or [""])[0]
        inst = next((i for i in instances() if i["name"] == name), None)
        if not inst:
            return self._send(404, json.dumps({"ok": False, "msg": f"Instanz '{name}' unbekannt"}))
        try:
            n = int(self.headers.get("Content-Length") or 0)
            patch = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
        before = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        ok, msg = patch_config(inst["config_file"], patch)
        restart = ok and str(patch.get("mode", "")).lower() not in ("", str(before.get("mode", "")).lower())
        print(f"[panel] {name}: {msg}", flush=True)
        self._send(200, json.dumps({"ok": ok, "msg": msg, "restart": restart}, ensure_ascii=False))

    def log_message(self, *a):
        pass  # eigenes, ruhigeres Logging oben


def main():
    print("=" * 66)
    print(" Prophos Copier-Panel")
    print(f" Ordner: {HERE}")
    print(f" Instanzen: {', '.join(i['name'] for i in instances()) or '(keine config*.json gefunden)'}")
    print(f" Im Browser oeffnen:  http://127.0.0.1:{PORT}")
    print(" Nur lokal erreichbar. Prophos wird nicht angefasst.")
    print("=" * 66)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nPanel beendet.")
    except OSError as e:
        sys.exit(f"Port {PORT} belegt oder blockiert: {e}")


if __name__ == "__main__":
    main()

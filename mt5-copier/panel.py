#!/usr/bin/env python3
"""
Prophos Copier-Panel — kleines Web-Frontend für den lokalen MT5-Copier auf DIESEM PC.

Zweck: Multiplikator, Symbol-Mapping, max_lots und Modus im Browser setzen statt in der
Textdatei — für mehrere Master/Prop-Firmen gleichzeitig. Zeigt außerdem live, was der
Copier pro Master gerade macht (Konten, offene Hedges, Log), und kann das jeweilige
Master-Terminal starten (MT5 merkt sich den Login pro Ordner — hier werden KEINE
Zugangsdaten gespeichert).

Bewusst eigenständig: Prophos (app.py / prophos.html) wird NICHT angefasst.

Technik:
  · Nur Python-Standardbibliothek — kein pip install, keine Cloud, keine Schlüssel.
  · Bindet ausschließlich an 127.0.0.1 — aus dem Netz nicht erreichbar.
  · Jede config*.json im Ordner ist ein Master (config.json, config-master2.json, …).
    Seit 13.08.2026 bedient EIN copier.py-Prozess alle Configs zugleich; der Status
    je Master liegt in der passenden status*.json.

Start:  python panel.py     →  http://127.0.0.1:8770
"""

import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

import provision

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PANEL_PORT", "8770"))

# Nur diese Felder darf das Panel schreiben. Terminal-Pfade, magic und die erwarteten
# Kontonummern bleiben tabu — das sind die Sicherheitsanker des Copiers.
WRITABLE = {"multiplier", "symbol_map", "max_lots_per_hedge", "mode"}
MODES = ("dryrun", "demo", "live")
# Dieselbe strenge Namensregel wie in copier.py — Explorer-Kopien wie
# "config - Kopie.json" oder "config (2).json" sind KEINE Instanz (Audit 13.08.2026:
# solche Karten sahen echt aus, steuerten aber nichts).
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")
SYMBOL_RE = re.compile(r"[A-Za-z0-9._#!&\-]{1,32}")


def instances():
    """Alle Master-Configs -> [{name, config_file, status_file}]. Schlüssel für alle
    API-Aufrufe ist config_file — der abgeleitete Name ist reine Anzeige (Audit-Fund:
    config-master2.json und config_master2.json ergaben denselben Namen, und der
    Save traf die falsche Datei)."""
    out = []
    for fn in sorted(os.listdir(HERE)):
        if fn in TEMPLATES or not CONFIG_RE.fullmatch(fn):
            continue
        name = fn[len("config"):-len(".json")].lstrip("-_") or "standard"
        out.append({"name": name, "config_file": fn,
                    "status_file": re.sub(r"^config", "status", fn, count=1, flags=re.I)})
    return out


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot():
    data, conflicts = [], []
    seen_magic, seen_snap = {}, {}
    for inst in instances():
        cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        magic = cfg.get("magic", 770001)
        snapf = str(cfg.get("snapshot_file", "prophos_master.csv")).lower()
        seen_magic.setdefault(magic, []).append(inst["config_file"])
        seen_snap.setdefault(snapf, []).append(inst["config_file"])
        data.append({
            "name": inst["name"],
            "file": inst["config_file"],
            "mode": cfg.get("mode"),
            "multiplier": cfg.get("multiplier"),
            "max_lots": cfg.get("max_lots_per_hedge"),
            "symbol_map": cfg.get("symbol_map") or {},
            "magic": magic,
            "snapshot_file": cfg.get("snapshot_file"),
            "master_expected": cfg.get("master_expected_login"),
            "hedge_expected": cfg.get("hedge_expected_login"),
            "has_terminal": bool(cfg.get("master_terminal_path")),
            "status": st,
            "age": age,
            # "lebt" = Statusdatei ist frisch. Der Copier schreibt alle ~3s.
            "alive": bool(st.get("running")) and age is not None and age <= 15,
        })
    # Konflikte, die der Copier beim Start mit Abbruch quittieren wuerde — hier
    # schon anzeigen, BEVOR jemand den Neustart auslöst.
    for magic, fs in seen_magic.items():
        if len(fs) > 1:
            conflicts.append(f"magic {magic} doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    for snapf, fs in seen_snap.items():
        if len(fs) > 1:
            conflicts.append(f"snapshot_file '{snapf}' doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    job = None
    if PROV_JOB:
        job = {"name": PROV_JOB["name"], "done": PROV_JOB["done"], "error": PROV_JOB["error"],
               "steps": [{"key": k, **PROV_JOB["steps"][k]} for k in PROV_STEPS]}
    return {"instances": data, "conflicts": conflicts, "job": job}


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
            if not isinstance(v, dict):
                return False, "symbol_map muss Text→Text sein"
            for a, b in v.items():
                if not isinstance(a, str) or not isinstance(b, str) \
                        or not SYMBOL_RE.fullmatch(a) or not SYMBOL_RE.fullmatch(b):
                    # Verengt auf Symbolzeichen — haelt auch Anfuehrungszeichen aus dem
                    # HTML fern (Audit-Fund: ein " im Symbolfeld verdrehte die Karte).
                    return False, f"Symbol ungueltig: '{a}' → '{b}'"
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


# ── Provisionierung: "Account hinzufuegen" ─────────────────────────────────────
# Ein Job zur Zeit. Das Passwort liegt NUR im Speicher des Worker-Threads und in
# der transienten Startdatei, die provision.py garantiert loescht — im Job-Status
# (den der Browser pollt) taucht es nie auf.
PROV_STEPS = ("pruefen", "klonen", "login", "ea", "neustart", "config")
PROV_LOCK = threading.Lock()
PROV_JOB = None  # {"name", "steps": {key: {"state", "note"}}, "error", "done"}


def prov_start(name, login, password, server):
    global PROV_JOB
    with PROV_LOCK:
        if PROV_JOB and not PROV_JOB.get("done"):
            return False, "Es laeuft schon eine Provisionierung — erst fertig laufen lassen."
        cfg = read_json(os.path.join(HERE, "config.json"), {}) or {}
        template = cfg.get("master_terminal_path") or ""
        job = {"name": name, "error": None, "done": False,
               "steps": {k: {"state": "pending", "note": None} for k in PROV_STEPS}}
        PROV_JOB = job

    def report(step, state, note=None):
        st = job["steps"].get(step)
        if st:
            st["state"] = state
            if note:
                st["note"] = note

    def worker():
        try:
            provision.run_provision(name=name, login=login, password=password,
                                    server=server, template_exe=template,
                                    folder=HERE, report=report)
        except provision.ProvisionError as e:
            job["error"] = str(e)
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        except Exception as e:  # unerwartet — trotzdem lesbar anzeigen
            job["error"] = f"{type(e).__name__}: {e}"
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        finally:
            job["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    return True, "gestartet"


def start_terminal(fname):
    """Startet das Master-Terminal der Instanz. Pfad kommt AUSSCHLIESSLICH aus der
    Config-Datei (nicht ueber die API setzbar) und muss eine terminal64.exe sein.
    MT5 laesst pro Datenordner nur eine Instanz zu — ein zweiter Start schadet nicht."""
    cfg = read_json(os.path.join(HERE, fname), {}) or {}
    path = str(cfg.get("master_terminal_path") or "").strip()
    if not path:
        return False, "master_terminal_path ist in der Config nicht gesetzt"
    if os.path.basename(path).lower() != "terminal64.exe":
        return False, "master_terminal_path muss auf eine terminal64.exe zeigen"
    if not os.path.exists(path):
        return False, f"nicht gefunden: {path}"
    try:
        subprocess.Popen([path], cwd=os.path.dirname(path))
        return True, "Terminal gestartet — Login kommt aus dem MT5-Ordner selbst"
    except OSError as e:
        return False, f"Start fehlgeschlagen: {e}"


PAGE = """<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Copier-Panel</title><style>
*{box-sizing:border-box}
body{margin:0;background:#12141a;color:#e7e9ee;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:14px 20px;border-bottom:1px solid #262a33;display:flex;align-items:center;gap:12px}
h1{font-size:16px;font-weight:600;margin:0}
.sub{color:#8b93a3;font-size:12px}
main{padding:18px 20px;display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(430px,1fr))}
.banner{grid-column:1/-1;background:#251715;border:1px solid #6b3630;color:#ffb3a7;
        padding:10px 12px;border-radius:10px;font-size:13px;white-space:pre-line}
.card{background:#181b22;border:1px solid #262a33;border-radius:12px;padding:16px}
.card.live{border-color:#6b3630}
.top{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.name{font-weight:600;font-size:15px}
.file{color:#6d7484;font-size:11px;margin-bottom:10px}
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
.acts{display:flex;gap:8px;margin-top:14px;align-items:center;flex-wrap:wrap}
.msg{font-size:12px;color:#7fd4a8;min-height:16px;flex:1}
.msg.err{color:#ffb3a7}
.dirty-hint{font-size:11px;color:#e8c268;display:none}
.card[data-dirty] .dirty-hint{display:inline}
pre{background:#0e1015;border:1px solid #22262f;border-radius:8px;padding:9px;margin:10px 0 0;font-size:11.5px;
    max-height:150px;overflow:auto;color:#9fa7b6;white-space:pre-wrap}
.warn{background:#251715;border:1px solid #6b3630;color:#ffb3a7;padding:8px 10px;border-radius:8px;font-size:12px;margin-top:10px}
.empty{color:#8b93a3;padding:30px 20px}
.card.add{border-style:dashed;border-color:#3a4150}
.steps{margin-top:12px;font-size:12.5px;display:grid;gap:4px}
.step{display:flex;gap:8px;align-items:baseline;color:#8b93a3}
.step .st{width:14px;text-align:center}
.step.done{color:#7fd4a8}.step.running{color:#e8c268}.step.error{color:#ffb3a7}
.step .note{color:#6d7484;font-size:11px}
</style></head><body>
<header><h1>Copier-Panel</h1><span class=sub>lokal auf diesem PC · ein Copier-Prozess für alle Master · Prophos bleibt unangetastet</span></header>
<main id=app><div class=empty>lade…</div></main>
<script>
const state={};
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function badge(m){const c=m==='live'?'b-live':m==='demo'?'b-demo':'b-dry';return `<span class="badge ${c}">${esc((m||'?').toUpperCase())}</span>`}
function mapRows(map){
  const e=Object.entries(map);
  return e.map(([k,v])=>`<div class=map>
    <input value="${esc(k)}" data-mk placeholder="Master-Symbol">
    <span>→</span>
    <input value="${esc(v)}" data-mv placeholder="Hedge-Symbol">
    <button class=x data-del title="Zeile entfernen">×</button></div>`).join('')
   +`<div class=map><input data-mk placeholder="neues Master-Symbol">
     <span>→</span><input data-mv placeholder="Hedge-Symbol"><span></span></div>`;
}
function card(d){
  const s=d.status||{}, live=d.alive;
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  return `<div class="card${d.mode==='live'?' live':''}" data-file="${esc(d.file)}">
   <div class=top><span class=name>${esc(d.name)}</span>${badge(d.mode)}
     <span class=sub style="margin-left:auto"><span class="dot ${live?'on':'off'}"></span>${live?'läuft':'gestoppt'}${d.age!=null?` · ${d.age}s`:''}</span></div>
   <div class=file>${esc(d.file)} · magic ${esc(d.magic)} · ${esc(d.snapshot_file||'?')}</div>
   <div class=kv>
     <span>Master</span><b>${esc(s.master_login||d.master_expected||'—')}</b>
     <span>Hedge</span><b>${esc(s.hedge_login||d.hedge_expected||'—')}</b>
     <span>Master-Positionen</span><b>${pos}</b>
     <span>offene Hedges</span><b>${hed}</b>
   </div>
   ${s.note?`<div class=warn>${esc(s.note)}</div>`:''}
   ${(s.blocked||[]).length?`<div class=warn>Gestoppt für Master-Pos: ${esc((s.blocked||[]).join(', '))} — im Hedge-Terminal prüfen</div>`:''}
   <div class=row>
     <div><label>Multiplikator</label><input type=number step=0.001 min=0 value="${esc(d.multiplier??'')}" data-f=multiplier></div>
     <div><label>max Lots pro Hedge</label><input type=number step=0.01 min=0 value="${esc(d.max_lots??'')}" data-f=max_lots_per_hedge></div>
   </div>
   <label>Modus</label>
   <select data-f=mode>
     <option value=dryrun ${d.mode==='dryrun'?'selected':''}>dryrun — nur mitlesen, keine Order</option>
     <option value=demo ${d.mode==='demo'?'selected':''}>demo — echte Order, nur Demo-Konto</option>
     <option value=live ${d.mode==='live'?'selected':''}>live — echtes Geld</option>
   </select>
   <label>Symbol-Mapping (Master → Hedge)</label>
   <div data-maps>${mapRows(d.symbol_map||{})}</div>
   <div class=acts><button data-save>Speichern &amp; pushen</button>
     ${d.has_terminal?`<button class=ghost data-term>Terminal starten</button>`:''}
     <span class=dirty-hint>ungespeicherte Änderung</span>
     <span class="msg"></span></div>
   <pre>${esc((s.log||[]).slice(-14).join('\\n')||'noch keine Log-Zeilen')}</pre>
  </div>`;
}
function addCard(job){
  const busy=job&&!job.done;
  const mark=s=>s.state==='done'?'✓':s.state==='running'?'…':s.state==='error'?'✗':'·';
  const labels={pruefen:'Prüfen & Kennwerte vergeben',klonen:'Terminal-Ordner klonen',
    login:'Erststart + Login (Zugangsdaten-Datei wird danach gelöscht)',
    ea:'Lese-EA + Preset einlegen',neustart:'Neustart — EA auf den Chart',config:'Config anlegen'};
  const steps=job?`<div class=steps>${job.steps.map(s=>`<div class="step ${s.state}"><span class=st>${mark(s)}</span>${labels[s.key]||s.key}${s.note?` <span class=note>${esc(s.note)}</span>`:''}</div>`).join('')}</div>`:'';
  const err=job&&job.error?`<div class=warn>${esc(job.error)}</div>`:'';
  const okmsg=job&&job.done&&!job.error?`<div class=steps><div class="step done"><span class=st>✓</span>fertig — Karte „${esc(job.name)}" erscheint gleich (dryrun)</div></div>`:'';
  return `<div class="card add" data-file="__add__">
   <div class=top><span class=name>＋ Account hinzufügen</span></div>
   <div class=file>klont das Master-Vorlage-Terminal, loggt ein, legt EA + Config an — alles automatisch</div>
   <div class=row>
     <div><label>Name (kurz, nur Buchstaben/Zahlen)</label><input data-p=name placeholder="z.B. ftmo1" ${busy?'disabled':''}></div>
     <div><label>Login (Kontonummer)</label><input data-p=login placeholder="z.B. 437899" ${busy?'disabled':''}></div>
   </div>
   <div class=row>
     <div><label>Passwort</label><input type=password data-p=password autocomplete=new-password ${busy?'disabled':''}></div>
     <div><label>Server</label><input data-p=server placeholder="z.B. FusionMarkets-Demo" ${busy?'disabled':''}></div>
   </div>
   <div class=acts><button data-prov ${busy?'disabled':''}>${busy?'läuft…':'Fertig — automatisch einrichten'}</button>
     <span class=msg id=prov-msg></span></div>
   ${steps}${err}${okmsg}
  </div>`;
}
async function load(){
  const r=await fetch('/api/instances'); const d=await r.json();
  const app=document.getElementById('app');
  const banner=d.conflicts.length?`<div class=banner>⛔ ${d.conflicts.map(esc).join('\\n⛔ ')}</div>`:'';
  d.instances.forEach(x=>state[x.file]=x);
  let b=app.querySelector('.banner'); if(b)b.remove();
  if(banner)app.insertAdjacentHTML('afterbegin',banner);
  const empty=app.querySelector('.empty'); if(empty)empty.remove();
  const files=new Set(d.instances.map(x=>x.file));
  app.querySelectorAll('.card').forEach(c=>{const f=c.getAttribute('data-file');if(f!=='__add__'&&!files.has(f))c.remove()});
  for(const x of d.instances){
    const cur=app.querySelector(`.card[data-file="${CSS.escape(x.file)}"]`);
    // Karten mit ungespeicherten Eingaben oder aktivem Fokus NICHT überschreiben —
    // der 3s-Reload hat sonst Dropdown-Auswahl und gelöschte Zeilen zurückgesetzt.
    if(cur&&(cur.hasAttribute('data-dirty')||cur.contains(document.activeElement)))continue;
    const html=card(x);
    if(cur){cur.outerHTML=html}else{
      const add=app.querySelector('.card.add');
      if(add)add.insertAdjacentHTML('beforebegin',html); else app.insertAdjacentHTML('beforeend',html);
    }
  }
  // Die Hinzufügen-Karte: nur neu zeichnen, wenn kein Feld fokussiert ist ODER ein Job läuft
  const addCur=app.querySelector('.card.add');
  const addHtml=addCard(d.job);
  if(!addCur)app.insertAdjacentHTML('beforeend',addHtml);
  else if((d.job&&!d.job.done)||!addCur.contains(document.activeElement))addCur.outerHTML=addHtml;
}
document.getElementById('app').addEventListener('input',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});
document.getElementById('app').addEventListener('change',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});
document.addEventListener('click',async e=>{
  const cardEl=e.target.closest&&e.target.closest('.card'); if(!cardEl)return;
  const file=cardEl.getAttribute('data-file');
  const msg=cardEl.querySelector('.msg');
  if(e.target.hasAttribute('data-del')){
    e.target.closest('.map').remove();
    cardEl.setAttribute('data-dirty','1');
    return;
  }
  if(e.target.hasAttribute('data-prov')){
    const get=k=>(cardEl.querySelector(`[data-p=${k}]`)||{}).value?.trim()||'';
    const body={name:get('name'),login:get('login'),password:(cardEl.querySelector('[data-p=password]')||{}).value||'',server:get('server')};
    if(!body.name||!body.login||!body.password||!body.server){
      msg.className='msg err';msg.textContent='Alle vier Felder ausfüllen.';return}
    if(!/^[A-Za-z0-9]{1,24}$/.test(body.name)){
      msg.className='msg err';msg.textContent='Name: nur Buchstaben/Zahlen, ohne Leer-/Bindezeichen.';return}
    msg.className='msg';msg.textContent='starte…';
    const r=await fetch('/api/provision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    const pw=cardEl.querySelector('[data-p=password]'); if(pw)pw.value='';
    msg.className='msg'+(d.ok?'':' err');
    msg.textContent=d.ok?'läuft — Fortschritt unten':('Fehler: '+d.msg);
    if(d.ok)setTimeout(load,1000);
    return;
  }
  if(e.target.hasAttribute('data-term')){
    msg.className='msg'; msg.textContent='starte Terminal…';
    const r=await fetch('/api/start-terminal?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    msg.className='msg'+(d.ok?'':' err'); msg.textContent=d.ok?d.msg:('Fehler: '+d.msg);
    return;
  }
  if(!e.target.hasAttribute('data-save'))return;
  const patch={};
  cardEl.querySelectorAll('[data-f]').forEach(el=>patch[el.getAttribute('data-f')]=el.value);
  const map={}; let bad=null, dup=null;
  cardEl.querySelectorAll('[data-maps] .map').forEach(row=>{
    const a=(row.querySelector('[data-mk]')||{}).value?.trim()||'';
    const b=(row.querySelector('[data-mv]')||{}).value?.trim()||'';
    if(!a&&!b)return;
    if(!a||!b){bad=a||b;return}
    if(map[a]!==undefined)dup=a;
    map[a]=b;
  });
  if(bad){msg.className='msg err';msg.textContent=`Fehler: Mapping-Zeile '${bad}' ist nur halb ausgefüllt`;return}
  if(dup){msg.className='msg err';msg.textContent=`Fehler: Master-Symbol '${dup}' doppelt im Mapping`;return}
  patch.symbol_map=map;
  if(patch.mode==='live'&&state[file]?.mode!=='live'){
    const s=state[file]||{};
    if(!confirm(`LIVE schalten — echtes Geld!\\n\\nDatei: ${file}\\nMaster: ${s.master_expected||'?'}\\nHedge: ${s.hedge_expected||'?'}\\n\\nDuplikum für dieses Paar ist aus?`)){
      msg.className='msg err';msg.textContent='Abgebrochen — Modus nicht geändert';return}
  }
  msg.className='msg'; msg.textContent='speichere…';
  const r=await fetch('/api/save?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const d=await r.json();
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?(d.msg+' — der Copier übernimmt es in ~2s'+(d.restart?' (Neustart läuft automatisch)':'')):('Fehler: '+d.msg);
  if(d.ok)cardEl.removeAttribute('data-dirty');
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

    def _local_ok(self):
        """Host/Origin auf 127.0.0.1|localhost festnageln — schuetzt gegen
        DNS-Rebinding und Requests fremder Seiten aus dem Browser heraus."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            return False
        origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin)
            if (o.hostname or "").lower() not in ("127.0.0.1", "localhost"):
                return False
        return True

    def do_GET(self):
        if not self._local_ok():
            return self._send(403, json.dumps({"error": "nur lokal"}))
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/instances":
            return self._send(200, json.dumps(snapshot(), ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self._local_ok():
            return self._send(403, json.dumps({"ok": False, "msg": "nur lokal"}))
        u = urlparse(self.path)
        ctype = (self.headers.get("Content-Type") or "")
        if "application/json" not in ctype:
            return self._send(400, json.dumps({"ok": False, "msg": "Content-Type muss application/json sein"}))
        if u.path == "/api/provision":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            name = str(body.get("name") or "").strip()
            login = str(body.get("login") or "").strip()
            password = str(body.get("password") or "")
            server = str(body.get("server") or "").strip()
            if not (name and login and password and server):
                return self._send(400, json.dumps({"ok": False, "msg": "Name, Login, Passwort und Server sind Pflicht."}))
            probs = provision.plan_checks(HERE, name, login, server,
                                          (read_json(os.path.join(HERE, "config.json"), {}) or {}).get("master_terminal_path"))
            if probs:
                return self._send(400, json.dumps({"ok": False, "msg": " · ".join(probs)}, ensure_ascii=False))
            ok, msg = prov_start(name, login, password, server)
            print(f"[panel] provision '{name}': {msg}", flush=True)  # bewusst ohne Zugangsdaten
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        fname = (parse_qs(u.query).get("file") or [""])[0]
        inst = next((i for i in instances() if i["config_file"] == fname), None)
        if not inst:
            return self._send(404, json.dumps({"ok": False, "msg": f"Instanz '{fname}' unbekannt"}))

        if u.path == "/api/start-terminal":
            ok, msg = start_terminal(inst["config_file"])
            print(f"[panel] {fname}: Terminal-Start → {msg}", flush=True)
            return self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        if u.path != "/api/save":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length") or 0)
            patch = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
        before = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        ok, msg = patch_config(inst["config_file"], patch)
        restart = ok and str(patch.get("mode", "")).lower() not in ("", str(before.get("mode", "")).lower())
        print(f"[panel] {fname}: {msg}", flush=True)
        self._send(200, json.dumps({"ok": ok, "msg": msg, "restart": restart}, ensure_ascii=False))

    def log_message(self, *a):
        pass  # eigenes, ruhigeres Logging oben


def main():
    print("=" * 66)
    print(" Prophos Copier-Panel")
    print(f" Ordner: {HERE}")
    print(f" Master: {', '.join(i['config_file'] for i in instances()) or '(keine config*.json gefunden)'}")
    ignored = [fn for fn in sorted(os.listdir(HERE))
               if fn.endswith(".json") and fn.lower().startswith("config")
               and fn not in TEMPLATES and not CONFIG_RE.fullmatch(fn)]
    if ignored:
        print(f" IGNORIERT (kein gueltiger Config-Name): {', '.join(ignored)}")
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

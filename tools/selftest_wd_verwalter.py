#!/usr/bin/env python3
"""Selbsttest WD-FARMER VERWALTER (30.10.2026, Slave 7; Finn als Emin: „Warum kann Emin nichts ändern? Der soll ja ändern können.").
(1) Echter JS-Code aus prophos.html (wdNurGruppe, wdVerwalter, wdSichtOk, wdNurLesen, wdKarteUid, wdDarf) läuft in JavaScriptCore mit
    gespielten Rollen: Verwalter Emin darf seine Gruppe, nie HT; HT-Admin alles; Mitglied ohne Code (eingeschränkt) nur die eigene ID.
(2) Verdrahtung: Karte/Chip/Handler/„Heute nicht drin" fragen wdNurLesen(uid), HT-weite Teile bleiben gesperrt (großes Würfeln,
    Reihenfolge, Risiko für alle, Einstellungen, SCHARF), „Änderungen speichern" + „Alle würfeln" sichtbar.
(3) SQL-Datei: wd_konto_setzen prüft den Besitz, wd_tagesplan/wd_farmer_regeln schreiben nur HT oder eigene Sicht.
Aufruf: python3 tools/selftest_wd_verwalter.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(HIER, "..", "sql", "2026-10-30_wd_verwalter_riegel.sql"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []
EMIN, AHMAD, MIKE, PASCAL = "emin-0001", "ahmad-002", "mike-0003", "pascal-04"


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


def bis(anfang, ende):
    i = HTML.index(anfang)
    return HTML[i:HTML.index(ende, i) + len(ende)]


def js_rollen():
    code = "\n".join([
        zeile("  async function wdNurGruppe(){"),
        zeile("  const wdVerwalter = () =>"),
        zeile("  const wdSichtOk = uid =>"),
        bis("  const wdNurLesen = uid =>", "window._wdNurLesen = uid => wdNurLesen(uid)"),
        bis("  async function wdDarf(uid, streng){", "\n  }\n"),
    ])
    # Rollen: verwalter = Klasse adm-verwalter am Admin-View; nur = _admNurGruppeLaden; ok = _admGruppeOk-Menge (null = Funktion fehlt)
    rollen = {
        "emin": {"ich": EMIN, "verwalter": True, "nur": True, "ok": [EMIN, AHMAD]},
        "ht": {"ich": PASCAL, "verwalter": False, "nur": False, "ok": [PASCAL, MIKE]},
        "mitglied": {"ich": AHMAD, "verwalter": False, "nur": True, "ok": None},
        "fehler": {"ich": AHMAD, "verwalter": False, "nur": "wirft", "ok": None},
    }
    prog = """
var window = {}, currentUserId = null, ROLLE = null
var document = { querySelector: function(s){ return (ROLLE && ROLLE.verwalter && s.indexOf('adm-verwalter') >= 0) ? {} : null } }
%s
var ROLLEN = %s, IDS = %s, aus = {}
var karte = function(uid){ return { closest: function(s){ return s === '.wd-karte' ? { dataset: { wdUser: uid } } : null } } }
var erwKarte = function(uid){ return { closest: function(s){ return s === '.wd-karte' ? { dataset: { wdErw: uid } } : null } } }
var faelle = []
for(var r in ROLLEN) faelle.push(r)
var lauf = async function(){
  for(var i = 0; i < faelle.length; i++){
    var name = faelle[i]; ROLLE = ROLLEN[name]; currentUserId = ROLLE.ich
    window._admNurGruppeLaden = ROLLE.nur === 'wirft' ? async function(){ throw new Error('x') } : (function(n){ return async function(){ return n } })(ROLLE.nur)
    if(ROLLE.ok) window._admGruppeOk = (function(m){ return function(u){ return m.indexOf(String(u)) >= 0 } })(ROLLE.ok); else delete window._admGruppeOk
    var e = { nurLesen: {}, darf: {}, streng: {} }
    for(var j = 0; j < IDS.length; j++){
      var u = IDS[j]
      e.nurLesen[u] = wdNurLesen(u); e.darf[u] = await wdDarf(u); e.streng[u] = await wdDarf(u, true)
    }
    e.karteUid = wdKarteUid(karte(AHMAD_ID)) + '|' + wdKarteUid(erwKarte(MIKE_ID)) + '|' + wdKarteUid(null)
    aus[name] = e
  }
  print(JSON.stringify(aus))
}
var AHMAD_ID = %s, MIKE_ID = %s
lauf().catch(function(e){ print('ERR ' + e) })
""" % (code, json.dumps(rollen), json.dumps([EMIN, AHMAD, MIKE, PASCAL]), json.dumps(AHMAD), json.dumps(MIKE))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(prog)
        pfad = f.name
    try:
        out = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60).stdout.strip()
    finally:
        os.unlink(pfad)
    if not out.startswith("{"):
        check(False, f"JS läuft in jsc ({out[:200]})")
        return None
    return json.loads(out)


def main():
    a = js_rollen()
    if a:
        e = a["emin"]
        check(not e["nurLesen"][EMIN] and not e["nurLesen"][AHMAD], "Emin: eigene ID + Gruppen-Mitglied Ahmad bedienbar (nicht nur Anzeige)")
        check(e["nurLesen"][MIKE] and e["nurLesen"][PASCAL], "Emin: HT-IDs (Mike, Pascal) bleiben nur Anzeige")
        check(e["darf"][EMIN] and e["darf"][AHMAD] and not e["darf"][MIKE] and not e["darf"][PASCAL], "Emin: wdDarf schreibt Gruppe, nie HT")
        check(e["streng"][EMIN] and not e["streng"][AHMAD], "Emin: Automatik am PC (streng) weiter nur die eigene Zeile")
        h = a["ht"]
        check(not any(h["nurLesen"].values()) and all(h["darf"].values()), "HT-Admin: unverändert alles bedienbar und schreibbar")
        m = a["mitglied"]
        check(m["darf"][AHMAD] and not m["darf"][EMIN] and not m["darf"][MIKE] and not m["darf"][PASCAL],
              "Mitglied ohne Code (eingeschränkt): schreibt nur die eigene ID, nichts der Gruppe, nichts von HT")
        check(not any(m["nurLesen"].values()), "Mitglied: kein Verwalter-Reiter — wdNurLesen greift nicht, der Riegel ist wdDarf (+ DB)")
        f = a["fehler"]
        check(f["darf"][AHMAD] and not f["darf"][MIKE] and not f["darf"][EMIN], "Einschränkung nicht prüfbar → wie eingeschränkt: nur eigene ID")
        check(e["karteUid"] == f"{AHMAD}|{MIKE}|", "wdKarteUid: ID aus data-wd-user bzw. data-wd-erw, ohne Karte leer")

    # (2) Verdrahtung
    karte = HTML[HTML.index("  function wdKarte(x, erw){"):HTML.index("  function wdSlotWaehlen(")]
    check("const nurLesen = wdNurLesen(x.user_id)" in karte and "wdVerwalter()" not in karte.split("const nurLesen")[1].split("const uid")[0],
          "wdKarte: nurLesen je ID (wdNurLesen), nicht mehr pauschal für Verwalter")
    check("const sperren = erw || fest || nurLesen ||" in karte and "const hakenSperre = fest || nurLesen ||" in karte
          and karte.count("${erw || fest || nurLesen ? 'disabled' : ''}") == 3 and "nur Anzeige — ändern kann Hermann Technologies" in karte,
          "wdKarte: Felder/Haken/BUY-SELL folgen nurLesen, Text „nur Anzeige“ nur noch bei fremder ID")
    chip = HTML[HTML.index("  function wdRichtungChip(x, erw){"):HTML.index("  async function wdRichtungUmschalten(")]
    check("if(fest || wdNurLesen(x.user_id))" in chip, "Richtungs-Chip: klickbar für IDs der Gruppe")
    hand = HTML[HTML.index("    box.querySelectorAll('[data-wd-drag]').forEach(g => {"):HTML.index("  function wdGruende(konten){")]
    check(hand.count("wdNurLesen(wdKarteUid(") == 5 and "if(!b.disabled && !wdNurLesen(b.dataset.wdFlip))" in hand,
          "Handler Haken/alle/nur heute/BUY-SELL/Zeilen-Klick fragen beim Klick wdNurLesen der Karte")
    check("if(wdVerwalter()) return ev.preventDefault();" in hand and "if(!_wd.drag || wdVerwalter()) return;" in hand
          and "const nachbar = (uid, richtung) => {   // ▲▼: Platz mit dem freien Nachbarn tauschen\n      if(wdVerwalter()) return" in hand,
          "Reihenfolge (Ziehen, ▲▼) bleibt HT-weit")
    sp = HTML[HTML.index("  async function wdSpeichern(){"):HTML.index("  async function wdRegelnSpeichern(")]
    check("if(_wd.umsortiert && _wd.umsortiert.size && !wdVerwalter())" in sp and "if(!(await wdDarf(el.dataset.wdUser))) continue" in sp,
          "wdSpeichern: Verwalter speichert nur Blöcke seiner Gruppe, nie eine Umsortierung")
    check(re.search(r'id="wdSave"(?![^>]*data-ht-global)', HTML) and re.search(r'id="wdNdAlle"(?![^>]*data-ht-global)', HTML)
          and re.search(r'id="wdWuerfel"[^>]*data-ht-global', HTML) and re.search(r'id="wdRiskAlle"[^>]*data-ht-global', HTML),
          "Knöpfe: „Änderungen speichern“ + „Alle würfeln“ sichtbar, großes 🎲 Würfeln + „für alle WD-Konten“ HT-weit")
    check("el.dataset.htGlobal = ''" in HTML and 'Einstellungen <span style="font-weight:400' in HTML
          and HTML.index('<div class="panel" style="margin:0 0 12px" data-ht-global>') < HTML.index('Einstellungen <span style="font-weight:400'),
          "SCHARF-Leiste und Einstellungen (Automatik, Zeitfenster, Firmen-Regeln) bleiben data-ht-global")
    nd = HTML[HTML.index("  function wdNdListe(){"):HTML.index("  function wdNdRender(){")]
    check("!wdNurLesen(kd.user_id)" in nd and "!wdSichtOk(kd.user_id)" in nd, "„Heute nicht drin“: 🎲 je Konto für Konten der Sicht/Gruppe")
    check("if(wdNurLesen(rein.dataset.wdNdUid) || _wd.busy) return" in HTML and "ev.stopPropagation(); wdNdAlle(); return" in HTML
          and "if(!(await wdDarf(uid))) return { fehler: 'nicht in deiner Gruppe' }" in HTML,
          "„Heute nicht drin“-Handler: Gruppe frei, wdKontoEinwuerfeln behält den wdDarf-Riegel")
    check("!wdNurLesen(x.user_id))" in HTML and "if(!wdNurLesen(rein.dataset.wdUebUid))" in HTML, "Überblick „heute rein“ für IDs der Gruppe")
    check("if(await wdNurGruppe()) return wdSay('Einstellungen gelten für alle IDs" in HTML, "wdRegelnSpeichern bleibt für Eingeschränkte gesperrt")

    # (3) SQL-Riegel
    s = re.sub(r"--[^\n]*", "", SQL)
    check("public.admin_nur_eigene() and v_owner not in (select s from public.admin_sichtbare_ids() s)" in s and "errcode = '42501'" in s
          and s.index("admin_nur_eigene()") < s.index("update public.accounts"),
          "SQL wd_konto_setzen: Besitz-Prüfung vor dem Update")
    reg = "(not (select public.admin_nur_eigene())) or user_id in (select s from public.admin_sichtbare_ids() s)"
    check('drop policy if exists "wd_tagesplan angemeldet"' in s and s.count(reg) == 4
          and 'for select to authenticated using (true)' in s, "SQL wd_tagesplan: lesen offen, insert/update/delete nur HT oder eigene Sicht")
    check('drop policy if exists "wd_farmer_regeln angemeldet"' in s
          and "using (not (select public.admin_nur_eigene())) with check (not (select public.admin_nur_eigene()))" in s,
          "SQL wd_farmer_regeln: schreiben nur HT")
    check(not re.search(r"\b(delete from|truncate|alter table)\b", s, re.I), "SQL ohne Datenänderung (nur Funktion + Policies)")

    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()

"""POLAR — Railway-Taktgeber (13.10.2026, Finn). EIGENES MODUL, bewusst (Finn: „nur an neuen Sachen arbeiten, alten Code in Ruhe
lassen"): app.py bekommt nur `import polar_app; polar_app.registrieren(app, globals())` — alles andere steht hier.

Funded-Futures (Master, ID A, TradingView, PC A) gegen Funded-CFD (Slave, ID B, MT5, PC B) als Airbag statt Fusion-Live.
  /polar/plan    Popup legt den Plan im Namen der Master-ID an (service role; der Slave gehört einer ANDEREN ID)
  /polar/start   PC-Tab des Masters startet den Lauf → polar_lauf-Zeile + order_signale an die Slave-ID (aktion polar_slave)
  /polar/bereit  Puls meldet „steht vor dem Klick"; sind BEIDE bereit, gibt es EINE Feuerzeit (jetzt + Vorlauf)
  /polar/warte   wartende Verbindung (auf=feuer | zu) — Zustand im Prozess (gunicorn --workers 1 --threads 48); „zu" der EINEN Seite
                 geht ohne Datenbank-Umweg in Millisekunden an die wartende Verbindung der ANDEREN Seite (seit 20.10.2026 beidseitig:
                 Finn „egal ob Master-PC A oder Slave-PC B, egal wer zuerst — schließt, schließt der andere in 1–2 s")
  /polar/melden  gefuellt / level / geparkt / zu (beide Seiten, erste Meldung gewinnt = zu_quelle, zweite = Bestätigung) / ende / abbruch / fehler
  /polar/stand   Anzeige (Tab) und Wiederaufnahme nach Railway-Neustart (Zustand aus polar_lauf)
  /polar/zeit    Uhrabgleich der Puls-Prozesse
  /polar/aktiv   Polar-Vorrang (20.10.2026): hält gerade ein Lauf (Bot oder Hand-Plan) die ID des Aufrufers? → Tab polarLaeuft()
  /polar/vorpruefung  Prüf-Tabelle vor dem Start (21.10.2026): Richtungsschutz, andere Trades/Signale, andere Polar-Läufe, beide PCs
  /polar/freigeben    „Polar starten" in der Tabelle: dieselben Prüfungen noch einmal, alles ✓ → Startzeit jetzt (der Master-PC startet)
  /polar/schritt      Live-Ablauf (21.10.2026): jede Bot-Phase je Seite mit Zeit + Zeile → Schrittliste im Lauf, /polar/stand liefert sie mit
Abbruch nur VOR der Feuerzeit; danach nur noch „fehler" (dann schließt die andere Seite ihre Position). Am Ende Balance/P&L beider
Seiten an Plan (review) und Konten — Finn: „im Nachhinein mit Balance ausgelesen, alles automatisch drin"."""
import re
import threading
import time
from datetime import datetime, timezone

from flask import request, jsonify, g

FEUER_VORLAUF_MS = 1500      # Feuerzeit = beide bereit + 1,5 s (Weg Railway → beide Puls → Druck)
BEREIT_FRIST_S = 75          # eine Seite bereit, die andere nach 75 s nicht → Abbruch (vor jeder Feuerzeit)
WARTE_MAX_S = 25             # wartende Verbindung höchstens 25 s, der Puls fragt sofort neu (gunicorn-Timeout 120 s)
# MANUELL ZUERST (16.10.2026, Finn: „Bis wir Polar automatisch nutzen, dauert es noch Wochen — ich will jetzt schon planen, speichern,
# starten, manuell beenden und bei ‚Erledigen' die P&Ls beider Accounts eingeben. Später automatisch, jetzt manuell."). Aus = kein Bot:
# /polar/plan setzt keine Startzeit (kein Start-Wächter am PC-Tab), „starten" legt den Plan gleich als laufend an, /polar/start antwortet
# 409. Der Bot-Weg (start/bereit/warte/melden) bleibt unverändert im Code — an = True setzen, wenn die Logik geprüft ist.
# BOT AN (21.10.2026, Finn über Master: „Finn will Polar per Bot starten können"): True. Ablauf nach Finns Live-Test 23:15 Dubai („Ich hab
# das Pop-up gespeichert und es hat insta den Account gestartet. Das soll nicht sein. Ich will den Plan speichern und dann ganz normal auf
# Starten drücken"): das Popup SPEICHERT nur (planned, ohne Startzeit). „Starten" am Plan öffnet die Prüf-Tabelle (/polar/vorpruefung);
# alles ✓ → „Polar starten" (/polar/freigeben setzt die Startzeit jetzt) → Start-Wächter am Master-PC → /polar/start (prüft fail-closed
# noch einmal) → Lauf + Auftrag an die Slave-ID. Hand-Polar bleibt: „Läuft" am Plan in Trades. Gleicher Schalter im Tab (prophos.html
# POLAR_AUTO). Zurück auf False = /polar/start antwortet wieder 409, der Tab startet nichts — Hand-Polar unverändert.
POLAR_AUTO = True
ENDE = ("fertig", "abbruch", "fehler")
_LAEUFE = {}
_COND = threading.Condition()
_AKTIV_CACHE = {}             # uid → (epoch, laeufe) — /polar/aktiv 5 s gecacht (Supabase-Diät, Master 20.10.2026)
SCHRITTE_MAX = 40             # Live-Ablauf: höchstens so viele Schritte je Seite (ein Lauf hat ~15)
SLAVE_LIVE_CACHE_S = 3        # Live-P&L des Slaves aus mt5_live höchstens alle 3 s je Lauf lesen (Supabase-Diät)
_SLAVE_LIVE = {}              # lauf_id → (epoch, {pl, at})
AKTIV_CACHE_S = 5
AKTIV_FENSTER_H = 36          # Läufe älter als 36 h zählen nicht mehr (Leiche nach Railway-Neustart ohne Ende-Meldung)
A = {}                        # Namensraum von app.py (sb_select, sb_update, sb_insert, _sb_anfrage, _sb_headers, SUPABASE_URL, …)


def _ms():
    return int(time.time() * 1000)


def _zahl(x):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _uuid(x):
    return bool(re.fullmatch(r"[0-9a-f-]{36}", str(x or "").strip().lower()))


def _db(lid, felder):
    """DB-Spiegel im Hintergrund — der Takt zwischen den PCs wartet nie auf Supabase."""
    def _los():
        try:
            A["sb_update"]("polar_lauf", {"id": f"eq.{lid}"}, felder)
        except Exception as e:
            print(f"[polar] ⚠️ DB {lid[:8]}: {type(e).__name__}: {str(e)[:120]}", flush=True)
    threading.Thread(target=_los, daemon=True).start()


def _laden(lid):
    """Zustand aus dem Prozess, sonst aus polar_lauf (nach einem Railway-Neustart). -> dict | None"""
    with _COND:
        z = _LAEUFE.get(lid)
    if z is not None or not _uuid(lid):
        return z
    try:
        rows = A["sb_select"]("polar_lauf", {"select": "*", "id": f"eq.{lid}", "limit": "1"})
    except Exception:
        return None
    if not rows:
        return None
    r = rows[0]
    z = {"id": lid, "plan_id": str(r.get("plan_id")), "master_uid": str(r.get("master_user_id")), "slave_uid": str(r.get("slave_user_id")),
         "status": r.get("status") or "start", "feuer_ms": r.get("feuer_ms"), "master_zu_ms": r.get("master_zu_ms"),
         "slave_zu_ms": r.get("slave_zu_ms"), "master": r.get("master") or {}, "slave": r.get("slave") or {}, "grund": r.get("grund"),
         "bereit": {}, "bereit_ms": {}, "angelegt_ms": 0}
    z.update(zu_erste_seite(z))      # wer zuerst zu war (20.10.2026) — aus den beiden Zeiten, ohne eigene Spalte
    with _COND:
        return _LAEUFE.setdefault(lid, z)


def schritt_eintragen(teil, phase, text, at_ms, maximal=SCHRITTE_MAX):
    """REIN RECHNEND (testbar, selftest_polar_riegel.py) — LIVE-ABLAUF (Finn 20.10.2026 ~23:55 Dubai: „… rechts Master, links Slave. Was die
    gerade genau machen: wird geöffnet, platziert, bereit zum Drücken — die ganzen Steps dahin schreiben"): Schritt an teil['schritte'] hängen,
    nach Zeit sortiert, Dublette (gleiche Phase + Zeit) weg, höchstens `maximal` (die jüngsten). → True, wenn neu."""
    liste = teil.setdefault("schritte", [])
    try:
        at = int(at_ms)
    except (TypeError, ValueError):
        at = _ms()
    ph = str(phase or "")[:30]
    if not ph or any(x.get("phase") == ph and x.get("at_ms") == at for x in liste):
        return False
    liste.append({"phase": ph, "text": str(text or "")[:160], "at_ms": at})
    liste.sort(key=lambda x: x.get("at_ms") or 0)
    if len(liste) > maximal:
        del liste[:len(liste) - maximal]
    return True


def slave_live_pl(rows, ticket):
    """REIN RECHNEND (testbar): Live-P&L des Slaves aus mt5_live-Zeilen des Slave-Logins ({updated_at, pos: master_positions}) — die
    Echo-Instanz meldet profit je Position (copier.py Snapshot). Jüngste Zeile mit dem Ticket → {pl, at} | None."""
    for r in sorted((x for x in rows or [] if isinstance(x, dict)), key=lambda x: str(x.get("updated_at") or ""), reverse=True):
        for q in (r.get("pos") or []):
            if isinstance(q, dict) and str(q.get("ticket")) == str(ticket) and q.get("profit") is not None:
                try:
                    return {"pl": round(float(q["profit"]), 2), "at": r.get("updated_at")}
                except (TypeError, ValueError):
                    return None
    return None


def _slave_live(z):
    """Live-P&L des Slaves für /polar/stand (3 s gecacht je Lauf). Nur, solange der Slave gefüllt und nicht beendet ist."""
    sl = z.get("slave") or {}
    ticket = (sl.get("gefuellt") or {}).get("ticket")
    login = str(((sl.get("auftrag") or {}).get("login")) or "")
    if not ticket or not login or sl.get("ende") or z.get("status") in ENDE:
        return None
    jetzt = time.time()
    c = _SLAVE_LIVE.get(z["id"])
    if c and jetzt - c[0] < SLAVE_LIVE_CACHE_S:
        return c[1]
    try:
        rows = A["sb_select"]("mt5_live", {"select": "updated_at,pos:status->master_positions", "master_login": f"eq.{login}",
                                           "order": "updated_at.desc", "limit": "3"}) or []
        wert = slave_live_pl(rows, ticket)
    except Exception:
        wert = None
    _SLAVE_LIVE[z["id"]] = (jetzt, wert)
    if len(_SLAVE_LIVE) > 50:
        for k in [k for k, v in _SLAVE_LIVE.items() if jetzt - v[0] > 120]:
            _SLAVE_LIVE.pop(k, None)
    return wert


def _sicht(z):
    return {"lauf_id": z["id"], "plan_id": z["plan_id"], "status": z["status"], "feuer_ms": z.get("feuer_ms"),
            "master_zu_ms": z.get("master_zu_ms"), "slave_zu_ms": z.get("slave_zu_ms"), "grund": z.get("grund"),
            "zu_ms": z.get("zu_ms"), "zu_quelle": z.get("zu_quelle"),   # erste zu-Meldung (20.10.2026, beidseitiges Schließen)
            "bereit": sorted(z.get("bereit") or {}), "server_ms": _ms(),
            "master": {k: v for k, v in (z.get("master") or {}).items() if k != "auftrag"},
            "slave": {k: v for k, v in (z.get("slave") or {}).items() if k != "auftrag"}}


def _seite_ok(z, uid, seite):
    return seite in ("master", "slave") and str(uid) == str(z["master_uid" if seite == "master" else "slave_uid"])


def _status(z, status, grund=None):
    """Unter _COND aufrufen. Weckt alle wartenden Verbindungen."""
    z["status"] = status
    if grund:
        z["grund"] = grund
    _COND.notify_all()


def _login_von_konto(acc):
    ext = str(acc.get("external_id") or "").strip()
    if re.fullmatch(r"\d{4,}", ext):
        return ext
    cl = str(acc.get("cred_login") or "").strip()
    return cl if re.fullmatch(r"\d{4,}", cl) else ""


def zu_erste_seite(z):
    """REIN RECHNEND (testbar): aus master_zu_ms/slave_zu_ms die erste zu-Meldung → {zu_ms, zu_quelle} (None/None = noch keine)."""
    m, s = z.get("master_zu_ms"), z.get("slave_zu_ms")
    if m is None and s is None:
        return {"zu_ms": None, "zu_quelle": None}
    if s is None or (m is not None and int(m) <= int(s)):
        return {"zu_ms": int(m), "zu_quelle": "master"}
    return {"zu_ms": int(s), "zu_quelle": "slave"}


def zu_eintragen(z, seite, daten, ms):
    """REIN RECHNEND (testbar): 'zu' einer Seite eintragen (20.10.2026, Finn: „egal wer zuerst — der andere schließt in 1–2 s").
    Die ERSTE Meldung gewinnt (zu_ms/zu_quelle = Signal an die andere Seite), die zweite ist nur die Bestätigung; eine Wiederholung
    derselben Seite ändert nichts. -> (db_felder, erste, neu)"""
    if seite not in ("master", "slave"):
        return {}, False, False
    feld = f"{seite}_zu_ms"
    if z.get(feld) is not None:
        return {}, False, False
    z[feld] = int(ms)
    z.setdefault(seite, {})["zu"] = daten if isinstance(daten, dict) else {}
    erste = z.get("zu_ms") is None
    if erste:
        z["zu_ms"], z["zu_quelle"] = int(ms), seite
    return {feld: int(ms)}, erste, True


def warte_zu_fertig(z, seite):
    """REIN RECHNEND (testbar): /polar/warte?auf=zu einer Seite ist fertig, sobald die ANDERE Seite zu gemeldet hat (oder der Lauf
    zu Ende ist). Master wartet auf slave_zu_ms, Slave auf master_zu_ms — das eigene 'zu' weckt die eigene Wache nie."""
    if z.get("status") in ENDE:
        return True
    gegen = "slave" if seite == "master" else "master"
    return z.get(f"{gegen}_zu_ms") is not None


def abrechnung_rechnen(z):
    """REIN RECHNEND (testbar): Ergebnis beider Seiten aus den Meldungen. -> dict"""
    m, s = z.get("master") or {}, z.get("slave") or {}
    me, se = m.get("ende") or {}, s.get("ende") or {}
    m_bs = _zahl(me.get("balance_start") or (m.get("gefuellt") or {}).get("balance_start") or (m.get("bereit") or {}).get("balance_start"))
    m_be = _zahl(me.get("balance_end"))
    master_pl = round(m_be - m_bs, 2) if m_bs is not None and m_be is not None else None
    wache = se.get("wache") or {}
    s_pl = _zahl(wache.get("profit"))
    s_bs, s_be = _zahl(se.get("balance_start") or wache.get("balance_start")), _zahl(wache.get("balance_end"))
    if s_pl is None and s_bs is not None and s_be is not None:
        s_pl = round(s_be - s_bs, 2)
    mg, sg = m.get("gefuellt") or {}, s.get("gefuellt") or {}
    return {"master_pl": master_pl, "slave_pl": s_pl, "master_balance_end": m_be, "master_equity_end": _zahl(me.get("equity_end")),
            "slave_balance_end": s_be, "slave_equity_end": _zahl(wache.get("equity_end")),
            "master_fill": _zahl(mg.get("fill")), "slave_fill": _zahl(sg.get("fill")), "slave_zu_weg": wache.get("zu_weg"),
            "verzug_ms": (int(z["slave_zu_ms"]) - int(z["master_zu_ms"])) if z.get("slave_zu_ms") and z.get("master_zu_ms") else None,
            "klick_abstand_ms": (abs(int(mg.get("klick_ms") or 0) - int(sg.get("klick_ms") or 0)) if mg.get("klick_ms") and sg.get("klick_ms") else None)}


def _abrechnen(z):
    """Am Ende: Plan → review mit P&L beider Seiten + Ergebnis in mt5_baseline.polar, Balances an beiden Konten. Im Hintergrund."""
    def _los():
        try:
            erg = abrechnung_rechnen(z)
            pid = z["plan_id"]
            rows = A["sb_select"]("trade_plans", {"select": "id,status,master_account_id,slave_account_id", "id": f"eq.{pid}", "limit": "1"})
            plan = rows[0] if rows else {}
            jetzt = A["_wt_now_iso"]()
            A["_sb_anfrage"]("POST", f"{A['SUPABASE_URL']}/rest/v1/rpc/mt5_baseline_patch", headers=A["_sb_headers"](), timeout=(5, 15),
                             json={"p_plan": pid, "p_patch": {"polar": dict(erg, lauf_id=z["id"], status=z["status"], at=jetzt)}, "p_status": None})
            upd = {"ended_at": jetzt}
            if erg["master_pl"] is not None:
                upd["master_pl"] = erg["master_pl"]
            if erg["slave_pl"] is not None:
                upd["slave_pl"] = erg["slave_pl"]
            if plan.get("status") == "open":
                upd["status"] = "review"
            A["sb_update"]("trade_plans", {"id": f"eq.{pid}", "status": "in.(open,review)"}, upd)
            if plan.get("master_account_id") and erg["master_balance_end"] is not None:
                A["sb_update"]("accounts", {"id": f"eq.{plan['master_account_id']}"},
                               {"tv_balance": erg["master_balance_end"], "tv_equity": erg["master_equity_end"], "tv_balance_at": jetzt, "tv_balance_quelle": "puls"})
            if plan.get("slave_account_id") and erg["slave_balance_end"] is not None:
                A["sb_update"]("accounts", {"id": f"eq.{plan['slave_account_id']}"},
                               {"tv_balance": erg["slave_balance_end"], "tv_equity": erg["slave_equity_end"], "tv_balance_at": jetzt, "tv_balance_quelle": "mt5"})
            print(f"[polar] ✅ {z['id'][:8]} abgerechnet: Master {erg['master_pl']} · Slave {erg['slave_pl']} · Verzug {erg['verzug_ms']} ms", flush=True)
        except Exception as e:
            print(f"[polar] ⚠️ Abrechnung {z['id'][:8]}: {type(e).__name__}: {str(e)[:160]}", flush=True)
    threading.Thread(target=_los, daemon=True).start()


def laeufe_aus_plaenen(rows):
    """REIN RECHNEND: trade_plans-Zeilen mit eingebettetem polar_lauf (PostgREST über den FK polar_lauf.plan_id, EIN Select) →
    Lauf-Zeilen im polar_lauf-Format für aktiv_liste (master/slave aus dem Plan, Ende-Status fällt dort raus)."""
    out = []
    for p in rows or []:
        if not isinstance(p, dict):
            continue
        for l in (p.get("polar_lauf") or []):
            if isinstance(l, dict):
                out.append({"id": l.get("id"), "plan_id": p.get("id"), "master_user_id": p.get("user_id"),
                            "slave_user_id": p.get("polar_slave_user_id"), "status": l.get("status"), "created_at": l.get("created_at")})
    return out


def aktiv_liste(uid, prozess_laeufe, db_laeufe, plaene):
    """REIN RECHNEND (testbar, selftest_polar_riegel.py): die Polar-Läufe, die ID uid gerade halten — Bot-Läufe (Prozess + polar_lauf,
    Status nicht in ENDE) und offene Hand-Polar-Pläne (route polar, status open; Finn 16.10.: „jetzt manuell"). Je Lauf eine Zeile mit
    seite (master|slave aus Sicht von uid), quelle (bot|hand), lauf_id (hand: None). Dubletten (Prozess + DB) fallen weg."""
    uid = str(uid or "")
    out, gesehen, fertig_ids = [], set(), set()
    for z in list(prozess_laeufe or []) + list(db_laeufe or []):
        if not isinstance(z, dict):
            continue
        lid = str(z.get("id") or z.get("lauf_id") or "")
        if str(z.get("status") or "") in ENDE:
            # VORRANG FÄLLT SOFORT MIT DEM LAUFENDE (Master-Nachtrag 21.10.2026, Finn 13.10.: „im Nachhinein mit Balance ausgelesen … alles
            # schon automatisch drin"): ein beendeter Prozess-Lauf überdeckt die noch nicht nachgezogene DB-Kopie (_db schreibt im Hintergrund)
            if lid:
                gesehen.add(lid)
                if str(z.get("status") or "") == "fertig":
                    fertig_ids.add(lid)
            continue
        mu, su = str(z.get("master_uid") or z.get("master_user_id") or ""), str(z.get("slave_uid") or z.get("slave_user_id") or "")
        if not lid or lid in gesehen or uid not in (mu, su):
            continue
        gesehen.add(lid)
        st = str(z.get("status") or "start")
        # SPERRE ERST AB DER ORDER (Finn 20.10.2026 02:30: „Sobald die Order platziert wurde, erst ab dann soll kein Puls mehr kommen"):
        # phase „vorbereiten" (start/bereit) sperrt im Tab noch nichts, „order" ab der Feuerzeit (feuer: gedrückt 1,5 s später; offen/zu danach)
        out.append({"lauf_id": lid, "plan_id": str(z.get("plan_id") or "") or None, "status": st,
                    "phase": "vorbereiten" if st in ("start", "bereit") else "order",
                    "seite": "master" if uid == mu else "slave", "quelle": "bot", "master_uid": mu, "slave_uid": su})
    plan_ids = {x["plan_id"] for x in out if x.get("plan_id")}
    for p in plaene or []:
        if not isinstance(p, dict) or str(p.get("route") or "") != "polar" or str(p.get("status") or "") != "open":
            continue
        # Bot-Plan nach SAUBEREM Ende (21.10.2026): ein Lauf „fertig" (beide Seiten gemeldet zu + Ende) gibt den offenen Plan sofort frei, bis
        # _abrechnen ihn auf review setzt. „fehler" NICHT (Prüfer S2 21.10.2026: der Bot meldet fehler gerade in UNKLAR-Fällen mit möglicher
        # offener Position — kein Fill-Beweis, „NICHT zu — SOFORT schließen") → der offene Plan hält weiter als Hand-Plan bis „Erledigt".
        # Laufende Bot-Läufe halten oben über ihren Lauf; nur abgebrochene Läufe (vor der Feuerzeit) ändern nichts.
        if any(isinstance(l, dict) and (str(l.get("status") or "") == "fertig" or str(l.get("id") or "") in fertig_ids) for l in (p.get("polar_lauf") or [])):
            continue
        pid = str(p.get("id") or "")
        mu, su = str(p.get("user_id") or ""), str(p.get("polar_slave_user_id") or "")
        if not pid or pid in plan_ids or uid not in (mu, su):
            continue
        plan_ids.add(pid)
        out.append({"lauf_id": None, "plan_id": pid, "status": "open", "phase": "order", "seite": "master" if uid == mu else "slave",
                    "quelle": "hand", "master_uid": mu, "slave_uid": su, "seit": p.get("started_at")})
    return out


VP_LESUNG_FENSTER_H = 2       # review ohne Lesung, beendet in den letzten 2 h → „wartet auf Lesung" (Puls liest gleich nach)
VP_SIGNAL_FENSTER_MIN = 15    # order_signale wartet/laeuft der letzten 15 min → „Puls-Signal läuft"
# READER AM MASTER-PC (Master-Nachtrag 21.10.2026, Finn 13.10.: „Sobald die Order auf dem Master-Account geschlossen wurde, liest das
# Tampermonkey-Script insta aus … innerhalb von maximal 1 bis 1,5 Sekunden an den zweiten Computer"): das Zu-Signal kommt vom LOKALEN Reader
# des Master-PCs (Port 8790, polar_bot master_wache liest /positions alle 50 ms) — der schreibt nichts nach tv_kurse, nur der 24/7-Kursfeed
# eines einzigen PCs tut das (Prüfer S2 21.10.2026, live belegt: tv_kurse frisch nur an einem PC, alle anderen ~19 T alt → die erste Fassung
# hätte jeden Start gesperrt). Darum hier nur eine Zeile „–" (vom Server nicht prüfbar, sperrt nicht); die PFLICHT-Prüfung macht polar_bot am
# Master-PC selbst vor dem Klick (reader_bereit): kein Reader → Abbruch vor der Feuerzeit, nichts gesendet.


def trades_belegt(rows, pid, jetzt):
    """REIN RECHNEND (testbar): trade_plans-Zeilen der Master- und Slave-ID → die, die gerade belegen: open = „läuft", review ohne Lesung
    (kein final/endlesung balance_end, kein today_pnl, nicht aufgegeben) und beendet ≤ VP_LESUNG_FENSTER_H = „wartet auf Lesung".
    Der Plan selbst und Polar-Pläne fallen raus (die prüft die Zeile „anderer Polar-Lauf"). jetzt = datetime UTC.
    big = Orbit-Big-Trade (trade_plans.orbit_v3, Orbit V3 mit Fusion-Hedge) — nur der sperrt den Polar-Start (Finn 21.10.2026).
    → [{user_id, id, route, name, art, big}]"""
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or str(r.get("id") or "") == str(pid) or str(r.get("route") or "") == "polar":
            continue
        st = str(r.get("status") or "")
        art = None
        if st == "open":
            art = "läuft"
        elif st == "review":
            fin = r.get("final") if isinstance(r.get("final"), dict) else {}
            el = r.get("endlesung") if isinstance(r.get("endlesung"), dict) else {}
            bn = r.get("bal_nach") if isinstance(r.get("bal_nach"), dict) else {}
            # Echo-Lesung steht in mt5_baseline.bal_nach (S2-Prüfung 21.10.2026: nur final zählte → Echo sperrte bis 2 h nach Ende)
            gelesen = fin.get("balance_end") is not None or el.get("balance_end") is not None or el.get("today_pnl") is not None \
                or bool(el.get("puls_aufgegeben")) or bool(fin.get("puls_aufgegeben")) or bn.get("ok") is True or bn.get("balance") is not None
            try:
                ende = datetime.fromisoformat(str(r.get("ended_at") or "").replace("Z", "+00:00"))
                frisch = (jetzt - ende).total_seconds() <= VP_LESUNG_FENSTER_H * 3600
            except ValueError:
                frisch = False
            if not gelesen and frisch:
                art = "wartet auf Lesung"
        if art:
            out.append({"user_id": str(r.get("user_id") or ""), "id": str(r.get("id") or ""), "route": str(r.get("route") or ""),
                        "name": str(r.get("master_name") or r.get("master_firm") or "")[:60], "art": art, "big": r.get("orbit_v3") is True})
    return out


def _vp_zeile(key, titel, ok, text, gruppe=None, seite=None):
    return {"key": key, "titel": titel, "ok": ok, "text": text, "gruppe": gruppe, "seite": seite}


def vorpruefung_zeilen(d):
    """REIN RECHNEND (testbar, selftest_polar_riegel.py) — PRÜF-TABELLE VOR DEM POLAR-START (Finn 21.10.2026 ~23:15 Dubai: „Wenn ich den
    Polar-Trade letztendlich starte, läuft eine Pre-Check-Tabelle, in der Richtungsschutz gecheckt wird … solange dieser Trade läuft, darf
    Puls nichts anderes machen … während ein Polar-Trade gestartet wird, darf auch kein Orbit-Trade laufen"). Tab-Tabelle, /polar/freigeben
    und /polar/start rechnen hiermit — die Tabelle ist nur die Anzeige, gestartet wird nur bei frei=True auf dem Server.
    d: rs_master/rs_slave (Antwort prophos_gegenrichtung_frei_konto oder {'fehler'}), m_name/s_name (Konten), m_wer/s_wer (IDs),
    mu/su (user_ids), belegt (trades_belegt; None = nicht lesbar), signale ([{user_id, aktion, status}]; None = nicht lesbar),
    polar ([aktiv_liste-Einträge ohne diesen Plan]; None = nicht lesbar), pc_master/pc_slave ({lebt, alt_s, pc_name} oder None = keine
    Zeile), pc_lesbar (bool), slave_ort ('da' | 'weg' | None), slave_login. Reader-Zeile immer „–" (prüft der Master-PC selbst).
    → (frei, zeilen[{key, titel, ok True|False|None, text}]). ok None = nicht prüfbar (zeigt sich, sperrt nur bei Richtung/Trades/Polar nie —
    die liefern bei Lesefehlern False = fail-closed); frei nur, wenn keine Zeile False ist."""
    # CROSSCHECK (Finn 21.10.2026 ~03:30 Dubai, Screenshot Vorprüfung Ina gegen Finn + Pascal: „Mach diese Prüfung ein bisschen schöner …
    # so wie ein Crosscheck"): jede Zeile trägt gruppe (Prüfung) + seite (master/slave, None = beide) — der Tab zeichnet Prüfung × Seite
    # (Slave links, Master rechts wie der Live-Ablauf). titel bleibt für die Fehlermeldung von /polar/start und /polar/freigeben.
    z = []
    for key, seite, erg, name in (("rs_master", "master", d.get("rs_master"), d.get("m_name")), ("rs_slave", "slave", d.get("rs_slave"), d.get("s_name"))):
        titel = f"Richtungsschutz {seite.capitalize()} · {name or seite.capitalize() + '-Konto'}"
        if isinstance(erg, dict) and erg.get("frei") is True:
            z.append(_vp_zeile(key, titel, True, "frei — keine Gegenrichtung an dieser ID × Firma", "richtung", seite))
        elif isinstance(erg, dict) and erg.get("frei") is False:
            z.append(_vp_zeile(key, titel, False, str(erg.get("grund") or "Gegenrichtung läuft")[:200], "richtung", seite))
        else:
            fehler = erg.get("fehler") if isinstance(erg, dict) else "keine Antwort"
            z.append(_vp_zeile(key, titel, False, f"nicht prüfbar: {fehler or 'unklar'} — nichts gestartet", "richtung", seite))
    # NUR BIG TRADES SPERREN (Finn 21.10.2026 ~03:30 Dubai: „Es soll ja nur kein Big Trade laufen … Es dürfen auf beiden IDs keine Orbit Trades
    # laufen"; Anlass: Ina hatte nur einen Auto-Planer-Challenge-Trade Orbit V2 45f5359b offen, Finn + Pascal einen Orbit V3 f7906bbe — beide
    # sperrten). Big Trade = trade_plans.orbit_v3 (läuft oder wartet auf Lesung) → ✗. Andere Trades stehen als Info dabei, sperren nicht.
    belegt, signale = d.get("belegt"), d.get("signale")
    for key, uid, wer, seite in (("big_master", d.get("mu"), d.get("m_wer"), "master"), ("big_slave", d.get("su"), d.get("s_wer"), "slave")):
        titel = f"Kein Big Trade (Orbit) · {seite.capitalize()}-ID {wer or '?'}"
        if belegt is None:
            z.append(_vp_zeile(key, titel, False, "nicht lesbar — nichts gestartet", "big", seite))
            continue
        tr = [b for b in belegt if str(b.get("user_id")) == str(uid)]
        big = [b for b in tr if b.get("big")]
        nebenbei = [b for b in tr if not b.get("big")]
        info = ("läuft auch: " + "; ".join(f"{b.get('name') or b.get('route') or '?'} ({b.get('art')})" for b in nebenbei) + " — kein Big Trade, sperrt nicht") if nebenbei else ""
        if big:
            z.append(_vp_zeile(key, titel, False, ("Big Trade " + "; ".join(f"{b.get('name') or '?'} ({b.get('art')})" for b in big))[:240], "big", seite))
        else:
            z.append(_vp_zeile(key, titel, True, ("frei" + (" · " + info if info else ""))[:300], "big", seite))
    # Puls-Signal in Arbeit (order_signale wartet/laeuft ≤ 15 min): der Puls dieser ID klickt gerade → bleibt Sperre (Panel wäre ohnehin belegt)
    for key, uid, wer, seite in (("puls_master", d.get("mu"), d.get("m_wer"), "master"), ("puls_slave", d.get("su"), d.get("s_wer"), "slave")):
        titel = f"Puls frei · {seite.capitalize()}-ID {wer or '?'}"
        if signale is None:
            z.append(_vp_zeile(key, titel, False, "nicht lesbar — nichts gestartet", "puls", seite))
            continue
        sg = [x for x in signale if str(x.get("user_id")) == str(uid) and str(x.get("aktion") or "") != "polar_slave"]
        z.append(_vp_zeile(key, titel, not sg, "frei — kein Puls-Signal in Arbeit" if not sg
                           else "Puls arbeitet: " + "; ".join(f"{x.get('aktion') or '?'} ({x.get('status')})" for x in sg)[:200], "puls", seite))
    pol = d.get("polar")
    if pol is None:
        z.append(_vp_zeile("polar", "Kein anderer Polar-Lauf", False, "nicht lesbar — nichts gestartet", "polar", None))
    else:
        z.append(_vp_zeile("polar", "Kein anderer Polar-Lauf", not pol,
                           "frei" if not pol else "läuft: " + "; ".join(f"{x.get('quelle')} {str(x.get('lauf_id') or x.get('plan_id') or '?')[:8]} ({x.get('seite')})" for x in pol)[:240],
                           "polar", None))
    for key, seite, wer, pc in (("pc_master", "master", d.get("m_wer"), d.get("pc_master")), ("pc_slave", "slave", d.get("s_wer"), d.get("pc_slave"))):
        titel = f"PC der {seite.capitalize()}-ID {wer or '?'}"
        if not d.get("pc_lesbar"):
            z.append(_vp_zeile(key, titel, None, "nicht prüfbar (PC-Stand nicht lesbar)", "pc", seite))
            continue
        if not pc or not pc.get("lebt"):
            alt = int((pc or {}).get("alt_s") or 0)
            z.append(_vp_zeile(key, titel, False, "aus — kein Prophos-Tab" + (f" seit {max(1, round(alt / 60))} min" if pc else " bekannt"), "pc", seite))
            continue
        z.append(_vp_zeile(key, titel, True, f"Tab lebt ({pc.get('pc_name') or '?'})" + (" — Panel + Puls-Chrome prüft der PC selbst beim Start" if seite == "master" else ""), "pc", seite))
    # Reader am Master-PC (e): vom Server nicht sichtbar (lokaler Port 8790) → „–", sperrt nicht; Pflicht-Prüfung im Bot vor dem Klick
    z.append(_vp_zeile("reader", f"Reader am Master-PC · {d.get('m_wer') or '?'}", None,
                       "Reader (Port 8790) prüft der Master-PC selbst vor dem Klick — ohne Reader bricht der Lauf ab, nichts gesendet", "geraet", "master"))
    # Slave-MT5 bereit (f): Instanz des Slave-Logins lebt am PC der Slave-ID (wie orderSignalTick polar_slave sie findet)
    ort, login = d.get("slave_ort"), d.get("slave_login") or "?"
    titel = f"Slave-MT5 bereit · Login {login}"
    if ort == "da":
        z.append(_vp_zeile("mt5_slave", titel, True, f"MT5 {login} läuft am PC der Slave-ID — Ein-Klick-Handel prüft der Bot selbst", "geraet", "slave"))
    elif ort == "weg":
        z.append(_vp_zeile("mt5_slave", titel, False, f"MT5 {login} auf keinem laufenden PC der Slave-ID eingerichtet bzw. Instanz schreibt nicht mehr", "geraet", "slave"))
    else:
        z.append(_vp_zeile("mt5_slave", titel, None, f"MT5 {login} nicht prüfbar (kein lebender PC mit Login-Stand)", "geraet", "slave"))
    for x in z:   # Spaltenkopf im Tab („Slave · Finn + Pascal")
        x["wer"] = d.get("m_wer") if x["seite"] == "master" else d.get("s_wer") if x["seite"] == "slave" else None
    return (not any(x["ok"] is False for x in z)), z


def richtungsschutz_pruefen(master_erg, slave_erg, master_name="Master-Konto", slave_name="Slave-Konto"):
    """REIN RECHNEND, fail-closed (Finn 20.10.2026 02:30: Richtungsschutz beim Polar-Start für BEIDE Konten): (frei, grund). frei nur,
    wenn beide Antworten der DB-Regel {'frei': true} tragen; eine Sperre nennt die Seite + den Grund der Regel, eine fehlende/kaputte
    Antwort sperrt ebenfalls („nicht prüfbar")."""
    for seite, erg, name in (("Master", master_erg, master_name), ("Slave", slave_erg, slave_name)):
        if isinstance(erg, dict) and erg.get("frei") is True:
            continue
        if isinstance(erg, dict) and erg.get("frei") is False:
            return False, f"Richtungsschutz {seite} ({name}): {erg.get('grund') or 'Gegenrichtung läuft'}"
        fehler = erg.get("fehler") if isinstance(erg, dict) else "keine Antwort"
        return False, f"Richtungsschutz {seite} ({name}) nicht prüfbar: {fehler or 'unklar'} — nichts gestartet"
    return True, ""


def _richtung_konto(uid, firma, richtung, ausser_plan=None, ausser_konto=None):
    """DB-Regel prophos_gegenrichtung_frei_konto (sql/2026-10-20_polar_richtungsschutz.sql, service role) → dict der Regel oder
    {'fehler': text}. Nie Exception — richtungsschutz_pruefen wertet fail-closed."""
    try:
        resp = A["_sb_anfrage"]("POST", f"{A['SUPABASE_URL']}/rest/v1/rpc/prophos_gegenrichtung_frei_konto", headers=A["_sb_headers"](),
                                timeout=(5, 15), json={"p_user": str(uid), "p_firma": firma or "", "p_richtung": richtung or "",
                                                       "p_ausser_plan": ausser_plan, "p_ausser_konto": ausser_konto})
    except Exception as e:
        return {"fehler": f"DB nicht erreichbar ({type(e).__name__})"}
    if resp.status_code == 404:
        return {"fehler": "DB-Funktion prophos_gegenrichtung_frei_konto fehlt — sql/2026-10-20_polar_richtungsschutz.sql einspielen"}
    if resp.status_code != 200:
        return {"fehler": f"DB-Antwort {resp.status_code}: {(resp.text or '')[:100]}"}
    try:
        erg = resp.json()
    except ValueError:
        return {"fehler": "DB-Antwort kein JSON"}
    return erg if isinstance(erg, dict) else {"fehler": "DB-Antwort unerwartet"}


def _vorpruefung(plan):
    """Liest alles für vorpruefung_zeilen (service role) → (frei, zeilen). Nie Exception: jede nicht lesbare Quelle wird zur Zeile
    (Richtung/Trades/Polar fail-closed, PCs „nicht prüfbar")."""
    pid, mu, su = str(plan.get("id") or ""), str(plan.get("user_id") or ""), str(plan.get("polar_slave_user_id") or "")
    jetzt_dt = datetime.now(timezone.utc)
    r = str(plan.get("richtung") or "").lower()
    gegen = "sell" if r == "buy" else "buy"
    d = {"mu": mu, "su": su, "m_name": plan.get("master_name"), "s_name": plan.get("slave_name")}
    try:
        namen = A["_ap_namen"]()[0]
    except Exception:
        namen = {}
    d["m_wer"], d["s_wer"] = namen.get(mu) or mu[:8], namen.get(su) or su[:8]
    s_acc = None
    try:
        s_acc = (A["sb_select"]("accounts", {"select": "id,user_id,firm,external_id,cred_login", "id": f"eq.{plan.get('slave_account_id')}"}) or [None])[0]
    except Exception:
        s_acc = None
    d["rs_master"] = _richtung_konto(mu, plan.get("master_firm"), r, pid, plan.get("master_account_id"))
    d["rs_slave"] = _richtung_konto(su, (s_acc or {}).get("firm") or plan.get("slave_firm"), gegen, pid, plan.get("slave_account_id")) \
        if s_acc and str(s_acc.get("user_id")) == su else {"fehler": "Slave-Konto passt nicht zur Slave-ID"}
    ids = ",".join(x for x in (mu, su) if _uuid(x))
    try:
        rows = A["sb_select"]("trade_plans", {"select": "id,user_id,route,status,master_name,master_firm,ended_at,orbit_v3,"
                                                        "endlesung:mt5_baseline->endlesung,final:mt5_baseline->final,bal_nach:mt5_baseline->bal_nach",
                                              "user_id": f"in.({ids})", "status": "in.(open,review)", "limit": "200"}) or []
        d["belegt"] = trades_belegt(rows, pid, jetzt_dt)
    except Exception:
        d["belegt"] = None
    try:
        ab = datetime.fromtimestamp(jetzt_dt.timestamp() - VP_SIGNAL_FENSTER_MIN * 60, timezone.utc).isoformat()
        d["signale"] = A["sb_select"]("order_signale", {"select": "id,user_id,status,created_at,aktion:params->>aktion", "user_id": f"in.({ids})",
                                                        "status": "in.(wartet,laeuft)", "created_at": f"gte.{ab}", "limit": "50"}) or []
    except Exception:
        d["signale"] = None
    try:
        prow = A["sb_select"]("trade_plans", {"select": "id,user_id,polar_slave_user_id,route,status,started_at,polar_lauf(id,status,created_at)",
                                              "route": "eq.polar", "status": "in.(planned,open)",
                                              "or": f"(user_id.in.({ids}),polar_slave_user_id.in.({ids}))", "order": "created_at.desc", "limit": "40"}) or []
        prow = [x for x in prow if str(x.get("id") or "") != pid]
        grenze = datetime.fromtimestamp(time.time() - AKTIV_FENSTER_H * 3600, timezone.utc).isoformat()
        dbl = [l for l in laeufe_aus_plaenen(prow) if str(l.get("created_at") or "9") >= grenze]
        with _COND:
            prozess = [dict(z) for z in _LAEUFE.values() if z.get("plan_id") != pid]
        gesehen, pol = set(), []
        for uid in (mu, su):
            for x in aktiv_liste(uid, prozess, dbl, prow):
                k = x.get("lauf_id") or x.get("plan_id")
                if k and k not in gesehen and str(x.get("plan_id") or "") != pid:
                    gesehen.add(k)
                    pol.append(x)
        d["polar"] = pol
    except Exception:
        d["polar"] = None
    stand = A["_ap_pc_stand_je"]()
    d["pc_lesbar"] = stand is not None
    d["pc_master"], d["pc_slave"] = (stand or {}).get(mu), (stand or {}).get(su)
    login = _login_von_konto(s_acc) if s_acc else ""
    d["slave_login"] = login
    try:
        mrows = A["sb_select"]("mt5_live", {"select": "pc_name,instance,master_login,updated_at,master_expected:status->>master_expected",
                                            "status->>user_id": f"eq.{su}", "limit": "200"})
        d["slave_ort"] = A["mt5_login_ort"](login, mrows, jetzt_dt)[0]
    except Exception:
        d["slave_ort"] = None
    return vorpruefung_zeilen(d)


def registrieren(app, ns):
    """Routen an die Flask-App hängen. ns = globals() von app.py (Supabase-Helfer, Auth)."""
    A.update(ns)

    @app.route("/polar/zeit", methods=["GET", "OPTIONS"])
    def polar_zeit():
        if request.method == "OPTIONS":
            return "", 200
        out = jsonify({"ok": True, "ms": _ms()})
        out.headers["Cache-Control"] = "no-store"
        return out

    @app.route("/polar/plan", methods=["POST", "OPTIONS"])
    def polar_plan():
        """Polar-Plan im Namen der Master-ID anlegen. Body: {master_account_id, slave_account_id, richtung, symbol, kontrakte, master_risk,
        slave_risk, lots, master_tp, master_sl, polar_pct, sl_pkt, tp_pkt, master_sl_pkt, master_tp_pkt, start_um?}.
        Seit 21.10.2026 (Finn: „Ich will den Plan speichern und dann ganz normal auf Starten drücken") NUR speichern: planned, ohne
        Startzeit — starten/hand im Body werden ignoriert. Start über „Starten" am Plan (Prüf-Tabelle → /polar/freigeben) oder von Hand („Läuft").
        Recht (16.10.2026) wie im übrigen Admin über die Sicht des Logins (_wd_login): unbeschränkt (Finn, Hermann Technologies) = alle IDs,
        Verwalter (Popup schickt sicht=admin) = seine Gruppe, eingeschränkte ID = nur sie selbst. Bis .1577 galt Admin nur über ADMIN_EMAILS
        (die Rechnungs-Liste) — Finn bekam „keine Berechtigung für diese IDs", sobald Master und Slave nicht ihm gehörten."""
        if request.method == "OPTIONS":
            return "", 200
        me, err = A["_wd_login"]()
        if err:
            return err
        d = request.get_json(silent=True) or {}
        ma, sa = str(d.get("master_account_id") or ""), str(d.get("slave_account_id") or "")
        if not _uuid(ma) or not _uuid(sa):
            return jsonify({"ok": False, "msg": "Master- und Slave-Konto fehlen"}), 400
        try:
            m_acc = (A["sb_select"]("accounts", {"select": "id,user_id,name,firm,account_type", "id": f"eq.{ma}"}) or [None])[0]
            s_acc = (A["sb_select"]("accounts", {"select": "id,user_id,name,firm,account_type,external_id,cred_login", "id": f"eq.{sa}"}) or [None])[0]
        except Exception as e:
            return jsonify({"ok": False, "msg": f"DB: {str(e)[:120]}"}), 503
        if not m_acc or not s_acc:
            return jsonify({"ok": False, "msg": "Master- oder Slave-Konto nicht gefunden"}), 404
        if m_acc.get("account_type") != "funded" or s_acc.get("account_type") != "funded_cfd":
            return jsonify({"ok": False, "msg": "Polar: Master = Funded Futures, Slave = Funded CFD"}), 400
        mu, su = str(m_acc["user_id"]), str(s_acc["user_id"])
        sicht = getattr(g, "admin_sicht", None)
        for uid, seite, acc in ((mu, "Master", m_acc), (su, "Slave", s_acc)):
            if not A["admin_in_sicht"](uid, sicht):
                return jsonify({"ok": False, "msg": f"{seite}-Konto „{acc.get('name') or acc['id'][:8]}\" gehört zu einer ID außerhalb deiner Sicht "
                                                    f"({'deine Gruppe' if getattr(g, 'admin_verwalter', False) else 'nur deine eigene ID'}) "
                                                    "→ Konto einer ID deiner Sicht wählen oder Finn planen lassen"}), 403
        r = str(d.get("richtung") or "").lower()
        kt, lots = _zahl(d.get("kontrakte")), _zahl(d.get("lots"))
        sl_pkt, tp_pkt = _zahl(d.get("sl_pkt")), _zahl(d.get("tp_pkt"))
        if r not in ("buy", "sell") or not kt or kt <= 0 or not lots or lots <= 0 or not sl_pkt or not tp_pkt:
            return jsonify({"ok": False, "msg": "Richtung, Kontrakte, Lots und Level fehlen"}), 400
        if not _login_von_konto(s_acc):
            return jsonify({"ok": False, "msg": "Slave-Konto ohne MT5-Login (External ID oder Login fehlt)"}), 400
        # Richtungsschutz beim Speichern nicht mehr (21.10.2026): gespeichert wird nur — geprüft wird beim Start (Prüf-Tabelle, /polar/start)
        zeile = {"user_id": mu, "master_account_id": m_acc["id"], "slave_account_id": s_acc["id"],
                 "master_name": m_acc.get("name"), "master_firm": m_acc.get("firm"), "slave_name": s_acc.get("name"), "slave_firm": s_acc.get("firm"),
                 "route": "polar", "status": "planned", "priority": "high", "richtung": r,
                 "master_symbol": str(d.get("symbol") or "").strip() or None, "master_contracts": kt, "master_risk": _zahl(d.get("master_risk")),
                 "slave_risk": _zahl(d.get("slave_risk")), "multiplier": round(lots / kt, 4),
                 "master_tp": _zahl(d.get("master_tp")), "master_sl": _zahl(d.get("master_sl")),
                 "polar_slave_user_id": su, "polar_pct": _zahl(d.get("polar_pct")) or 102.5,
                 # Dubai-Tag statt UTC (21.10.2026, Finn fand seine zwei Polar-Pläne von 03:20 Dubai nicht: planned_for stand auf dem
                 # UTC-Vortag 20.10. — Karte am falschen Tag, und der Tages-Reset im Nachtlauf räumt planned_for < Zieltag ab)
                 "planned_for": (A["_kapitel_heute_iso"]() if "_kapitel_heute_iso" in A else datetime.now(timezone.utc).date().isoformat()),
                 "mt5_baseline": {"polar_auftrag": {"lots": lots, "sl_pkt": sl_pkt, "tp_pkt": tp_pkt, "kontrakte": kt,
                                                    "master_sl_pkt": _zahl(d.get("master_sl_pkt")), "master_tp_pkt": _zahl(d.get("master_tp_pkt"))}}}
        try:
            neu = A["sb_insert"]("trade_plans", zeile)
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Plan nicht angelegt: {str(e)[:200]}"}), 400
        return jsonify({"ok": True, "plan_id": str((neu or {}).get("id") or ""), "master_uid": mu, "slave_uid": su,
                        "status": zeile["status"], "auto": False})

    def _vp_plan(d):
        """Plan + Sicht für Prüf-Tabelle und Freigabe → (plan, None) oder (None, antwort)."""
        pid = str((d or {}).get("plan_id") or "").strip().lower()
        if not _uuid(pid):
            return None, (jsonify({"ok": False, "msg": "plan_id fehlt"}), 400)
        try:
            plan = (A["sb_select"]("trade_plans", {"select": "*", "id": f"eq.{pid}", "limit": "1"}) or [None])[0]
        except Exception as e:
            return None, (jsonify({"ok": False, "msg": f"DB: {str(e)[:120]}"}), 503)
        if not plan or plan.get("route") != "polar":
            return None, (jsonify({"ok": False, "msg": "kein Polar-Plan"}), 404)
        sicht = getattr(g, "admin_sicht", None)
        for uid in (plan.get("user_id"), plan.get("polar_slave_user_id")):
            if not A["admin_in_sicht"](str(uid), sicht):
                return None, (jsonify({"ok": False, "msg": "Master- oder Slave-ID außerhalb deiner Sicht"}), 403)
        return plan, None

    # PRÜF-TABELLE (Finn 21.10.2026 ~23:15 Dubai: „Wenn ich den Polar-Trade letztendlich starte, läuft eine Pre-Check-Tabelle …"): nur lesen.
    @app.route("/polar/vorpruefung", methods=["POST", "OPTIONS"])
    def polar_vorpruefung():
        if request.method == "OPTIONS":
            return "", 200
        _me, err = A["_wd_login"]()
        if err:
            return err
        plan, fehler = _vp_plan(request.get_json(silent=True))
        if fehler:
            return fehler
        frei, zeilen = _vorpruefung(plan)
        out = jsonify({"ok": True, "frei": frei, "zeilen": zeilen, "status": plan.get("status"), "start_um": plan.get("start_um")})
        out.headers["Cache-Control"] = "no-store"
        return out

    # „Polar starten" in der Prüf-Tabelle: dieselben Prüfungen auf dem Server, alles ✓ → Startzeit jetzt; der Start-Wächter am Master-PC
    # claimt und ruft /polar/start (prüft dort ein drittes Mal). Nur ein geplanter, noch nicht geclaimter Plan.
    @app.route("/polar/freigeben", methods=["POST", "OPTIONS"])
    def polar_freigeben():
        if request.method == "OPTIONS":
            return "", 200
        _me, err = A["_wd_login"]()
        if err:
            return err
        if not POLAR_AUTO:
            return jsonify({"ok": False, "msg": "Polar-Bot ist aus (POLAR_AUTO) — von Hand starten („Läuft“)"}), 409
        plan, fehler = _vp_plan(request.get_json(silent=True))
        if fehler:
            return fehler
        if plan.get("status") != "planned" or plan.get("start_um_gestartet_at"):
            return jsonify({"ok": False, "msg": f"Plan steht auf {plan.get('status')}{' · schon gestartet' if plan.get('start_um_gestartet_at') else ''}"}), 409
        frei, zeilen = _vorpruefung(plan)
        if not frei:
            return jsonify({"ok": False, "code": "vorpruefung", "msg": "Vorprüfung nicht grün", "zeilen": zeilen}), 409
        try:
            neu = A["sb_update"]("trade_plans", {"id": f"eq.{plan['id']}", "status": "eq.planned", "start_um_gestartet_at": "is.null"},
                                 {"start_um": A["_wt_now_iso"]()})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Startzeit nicht gesetzt: {str(e)[:160]}"}), 502
        if not neu:
            return jsonify({"ok": False, "msg": "Plan war nicht mehr geplant — nichts gesetzt"}), 409
        return jsonify({"ok": True, "frei": True, "zeilen": zeilen, "plan_id": str(plan["id"])})

    @app.route("/polar/geblowt", methods=["POST", "OPTIONS"])
    def polar_geblowt():
        """Polar manuell (16.10.2026, Finn: „je Seite ein eigener Haken geblowt"): Konten eines Polar-Plans, die einer ANDEREN ID gehören, im
        Archiv ihres Besitzers als geblowt eintragen (_konto_archiv_eintragen wie das Radar-Abhaken) — der Tab schreibt nur sein eigenes Archiv.
        Body {plan_id, account_ids}. Nur Master-/Slave-Konto dieses Plans, nur IDs in der Sicht des Logins."""
        if request.method == "OPTIONS":
            return "", 200
        _me, err = A["_wd_login"]()
        if err:
            return err
        d = request.get_json(silent=True) or {}
        pid = str(d.get("plan_id") or "").strip().lower()
        ids = [str(x).strip().lower() for x in (d.get("account_ids") or []) if _uuid(x)]
        if not _uuid(pid) or not ids:
            return jsonify({"ok": False, "msg": "plan_id oder Konten fehlen"}), 400
        try:
            plan = (A["sb_select"]("trade_plans", {"select": "id,route,master_account_id,slave_account_id", "id": f"eq.{pid}", "limit": "1"}) or [None])[0]
        except Exception as e:
            return jsonify({"ok": False, "msg": f"DB: {str(e)[:120]}"}), 503
        if not plan or plan.get("route") != "polar":
            return jsonify({"ok": False, "msg": "kein Polar-Plan"}), 404
        erlaubt = {str(plan.get("master_account_id") or "").lower(), str(plan.get("slave_account_id") or "").lower()}
        sicht = getattr(g, "admin_sicht", None)
        jetzt = A["_wt_now_iso"]()
        erg = []
        for aid in ids:
            if aid not in erlaubt:
                return jsonify({"ok": False, "msg": f"Konto {aid[:8]} gehört nicht zu diesem Plan"}), 400
            try:
                acc = (A["sb_select"]("accounts", {"select": "id,user_id,name", "id": f"eq.{aid}", "limit": "1"}) or [None])[0]
                if not acc:
                    return jsonify({"ok": False, "msg": f"Konto {aid[:8]} nicht gefunden"}), 404
                if not A["admin_in_sicht"](acc.get("user_id"), sicht):
                    return jsonify({"ok": False, "msg": f"Konto „{acc.get('name') or aid[:8]}\" gehört zu einer ID außerhalb deiner Sicht"}), 403
                neu_arch = A["_konto_archiv_eintragen"](str(acc["user_id"]), aid, "blown", jetzt, acc.get("name"))
            except Exception as e:
                return jsonify({"ok": False, "msg": f"Archiv: {type(e).__name__}: {str(e)[:120]}"}), 502
            erg.append({"account_id": aid, "neu": bool(neu_arch)})
        return jsonify({"ok": True, "archiviert": erg})

    @app.route("/polar/start", methods=["POST", "OPTIONS"])
    def polar_start():
        """PC-Tab der Master-ID: Lauf anlegen + Auftrag an die Slave-ID. Body {plan_id}."""
        if request.method == "OPTIONS":
            return "", 200
        if not POLAR_AUTO:
            return jsonify({"ok": False, "msg": "Polar läuft manuell (POLAR_AUTO aus) — kein Bot-Start; Plan in Trades von Hand führen"}), 409
        me, err = A["_wd_login"]()
        if err:
            return err
        pid = str((request.get_json(silent=True) or {}).get("plan_id") or "").strip().lower()
        if not _uuid(pid):
            return jsonify({"ok": False, "msg": "plan_id fehlt"}), 400
        try:
            plan = (A["sb_select"]("trade_plans", {"select": "*", "id": f"eq.{pid}", "limit": "1"}) or [None])[0]
        except Exception as e:
            return jsonify({"ok": False, "msg": f"DB: {str(e)[:120]}"}), 503
        if not plan or plan.get("route") != "polar":
            return jsonify({"ok": False, "msg": "kein Polar-Plan"}), 404
        if str(plan.get("user_id")) != str(me):
            return jsonify({"ok": False, "msg": "Polar startet nur am PC der Master-ID"}), 403
        if plan.get("status") != "planned":
            return jsonify({"ok": False, "msg": f"Plan steht auf {plan.get('status')}"}), 409
        with _COND:
            laeuft = next((z for z in _LAEUFE.values() if z["plan_id"] == pid and z["status"] not in ENDE), None)
        if laeuft:
            return jsonify({"ok": True, "schon": True, "master": laeuft["master"].get("auftrag"), **_sicht(laeuft)})
        auftrag = ((plan.get("mt5_baseline") or {}).get("polar_auftrag") or {})
        try:
            s_acc = (A["sb_select"]("accounts", {"select": "id,user_id,firm,external_id,cred_login", "id": f"eq.{plan.get('slave_account_id')}"}) or [None])[0]
        except Exception as e:
            return jsonify({"ok": False, "msg": f"DB: {str(e)[:120]}"}), 503
        if not s_acc or str(s_acc.get("user_id")) != str(plan.get("polar_slave_user_id")):
            return jsonify({"ok": False, "msg": "Slave-Konto passt nicht zur Slave-ID"}), 400
        # VORPRÜFUNG (Finn 21.10.2026 ~23:15 Dubai, s. vorpruefung_zeilen): dieselbe Tabelle wie im Tab, hier fail-closed — Richtungsschutz
        # beider Konten (vorher allein, 20.10.2026 02:30), keine anderen Trades/Signale an beiden IDs, kein anderer Polar-Lauf, beide PCs
        frei, zeilen = _vorpruefung(plan)
        if not frei:
            nein = [z for z in zeilen if z["ok"] is False]
            return jsonify({"ok": False, "code": "vorpruefung", "msg": "; ".join(f"{z['titel']}: {z['text']}" for z in nein)[:400], "zeilen": zeilen}), 409
        s_richtung = "sell" if plan.get("richtung") == "buy" else "buy"
        slave_auftrag = {"account_id": s_acc["id"], "login": _login_von_konto(s_acc), "firm": s_acc.get("firm"), "richtung": s_richtung,
                         "volumen": auftrag.get("lots"), "sl_pkt": auftrag.get("sl_pkt"), "tp_pkt": auftrag.get("tp_pkt")}
        master_auftrag = {"richtung": plan.get("richtung"), "kontrakte": auftrag.get("kontrakte") or plan.get("master_contracts"),
                          "symbol": plan.get("master_symbol"), "sl_pkt": auftrag.get("master_sl_pkt"), "tp_pkt": auftrag.get("master_tp_pkt"),
                          "tp_usd": plan.get("master_tp"), "sl_usd": plan.get("master_sl")}
        try:
            row = A["sb_insert"]("polar_lauf", {"plan_id": pid, "master_user_id": str(me), "slave_user_id": str(plan["polar_slave_user_id"]),
                                                "master": {"auftrag": master_auftrag}, "slave": {"auftrag": slave_auftrag}})
            lid = str(row["id"])
            # plan_id bewusst „polar:<lauf>" (keine UUID): der Gegenrichtungs-Riegel auf order_signale prüft nur Plan-UUIDs derselben ID —
            # der Slave ist eine ANDERE ID bei einer anderen Firma
            A["sb_insert"]("order_signale", {"user_id": str(plan["polar_slave_user_id"]), "plan_id": f"polar:{lid}", "status": "wartet",
                                             "params": {"aktion": "polar_slave", "lauf_id": lid, "plan_id": pid, **slave_auftrag}})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Lauf nicht angelegt: {str(e)[:200]}"}), 503
        z = {"id": lid, "plan_id": pid, "master_uid": str(me), "slave_uid": str(plan["polar_slave_user_id"]), "status": "start",
             "feuer_ms": None, "master_zu_ms": None, "slave_zu_ms": None, "master": {"auftrag": master_auftrag}, "slave": {"auftrag": slave_auftrag},
             "grund": None, "bereit": {}, "bereit_ms": {}, "angelegt_ms": _ms()}
        with _COND:
            _LAEUFE[lid] = z
        print(f"[polar] ▶ Lauf {lid[:8]} Plan {pid[:8]} Master {str(me)[:8]} → Slave {str(plan['polar_slave_user_id'])[:8]}", flush=True)
        return jsonify({"ok": True, "lauf_id": lid, "master": master_auftrag, "slave": slave_auftrag, "server_ms": _ms()})

    @app.route("/polar/bereit", methods=["POST"])
    def polar_bereit():
        wer = A["_code_zugang"]()
        if not wer:
            return jsonify({"ok": False, "msg": "kein gültiger Schlüssel"}), 403
        d = request.get_json(silent=True) or {}
        lid, seite = str(d.get("lauf_id") or ""), str(d.get("seite") or "")
        z = _laden(lid)
        if not z or not _seite_ok(z, wer[0], seite):
            return jsonify({"ok": False, "msg": "Lauf/Seite passt nicht"}), 403
        neu_feuer = False
        with _COND:
            if z["status"] in ENDE:
                return jsonify({"ok": False, **_sicht(z)})
            z["bereit"][seite] = wer[1]
            z["bereit_ms"][seite] = _ms()
            z.setdefault(seite, {})["bereit"] = d.get("daten") if isinstance(d.get("daten"), dict) else {}
            if z.get("feuer_ms") is None and "master" in z["bereit"] and "slave" in z["bereit"]:
                z["feuer_ms"] = _ms() + FEUER_VORLAUF_MS
                neu_feuer = True
                _status(z, "feuer")
            elif z["status"] == "start":
                _status(z, "bereit")
            else:
                _COND.notify_all()
            sicht = _sicht(z)
        _db(lid, {"status": z["status"], f"{seite}_bereit_at": A["_wt_now_iso"](), **({"feuer_ms": z["feuer_ms"]} if neu_feuer else {})})
        return jsonify({"ok": True, **sicht})

    @app.route("/polar/warte", methods=["GET"])
    def polar_warte():
        """auf=feuer → kommt mit feuer_ms (oder Abbruch); auf=zu → kommt, sobald der Master flach ist oder der Lauf mit Fehler endet.
        Höchstens WARTE_MAX_S, dann {warte:true} — sofort neu fragen."""
        wer = A["_code_zugang"]()
        if not wer:
            return jsonify({"ok": False, "msg": "kein gültiger Schlüssel"}), 403
        lid, seite, auf = request.args.get("lauf_id") or "", request.args.get("seite") or "", request.args.get("auf") or "feuer"
        z = _laden(lid)
        if not z or not _seite_ok(z, wer[0], seite):
            return jsonify({"ok": False, "msg": "Lauf/Seite passt nicht"}), 403
        max_s = _zahl(request.args.get("max_s")) or WARTE_MAX_S
        ende = time.time() + min(WARTE_MAX_S, max(1.0, max_s))

        def fertig():
            if z["status"] in ENDE:
                return True
            if auf == "feuer":
                return z.get("feuer_ms") is not None
            if auf == "zu":
                return warte_zu_fertig(z, seite)      # beidseitig (20.10.2026): die andere Seite ist zu
            return True
        with _COND:
            while not fertig():
                if z.get("feuer_ms") is None and z.get("bereit_ms"):
                    if _ms() - min(z["bereit_ms"].values()) > BEREIT_FRIST_S * 1000:
                        _status(z, "abbruch", "andere Seite nicht bereit")
                        _db(lid, {"status": "abbruch", "grund": z["grund"]})
                        break
                rest = ende - time.time()
                if rest <= 0:
                    break
                _COND.wait(timeout=min(rest, 1.0))
            sicht = _sicht(z)
            noch = not fertig()
        out = jsonify({"ok": True, "warte": noch, **sicht})
        out.headers["Cache-Control"] = "no-store"
        return out

    @app.route("/polar/melden", methods=["POST"])
    def polar_melden():
        """Ereignisse der Puls-Prozesse. zu (Master flach) weckt SOFORT die wartende Slave-Verbindung — DB danach im Hintergrund."""
        wer = A["_code_zugang"]()
        if not wer:
            return jsonify({"ok": False, "msg": "kein gültiger Schlüssel"}), 403
        d = request.get_json(silent=True) or {}
        lid, seite, ereignis = str(d.get("lauf_id") or ""), str(d.get("seite") or ""), str(d.get("ereignis") or "")
        daten = d.get("daten") if isinstance(d.get("daten"), dict) else {}
        z = _laden(lid)
        if not z or not _seite_ok(z, wer[0], seite):
            return jsonify({"ok": False, "msg": "Lauf/Seite passt nicht"}), 403
        db, abrechnen, plan_open = {}, False, False
        with _COND:
            teil = z.setdefault(seite, {})
            if ereignis == "zu":
                # BEIDE SEITEN (20.10.2026): erste Meldung gewinnt und weckt die wartende Gegenseite (Status master_zu | slave_zu),
                # die zweite ist die Bestätigung (nur Zeit eintragen, nichts wecken außer /polar/stand-Lesern)
                db, erste, neu = zu_eintragen(z, seite, daten, _ms())
                if neu:
                    if erste and z["status"] not in ENDE:
                        _status(z, f"{seite}_zu")
                    else:
                        _COND.notify_all()
                    db["status"] = z["status"]
            elif ereignis == "abbruch":
                if z.get("feuer_ms") is not None:
                    return jsonify({"ok": False, "msg": "schon gefeuert — nur noch 'fehler'", **_sicht(z)}), 409
                if z["status"] not in ENDE:
                    _status(z, "abbruch", f"{seite}: {str(daten.get('grund') or 'abgebrochen')[:120]}")
                    db = {"status": "abbruch", "grund": z["grund"]}
            elif ereignis == "fehler":
                teil["fehler"] = daten
                if z["status"] not in ENDE:
                    _status(z, "fehler", f"{seite}: {str(daten.get('msg') or 'Fehler')[:160]}")
                else:
                    _COND.notify_all()
                db = {"status": z["status"], "grund": z["grund"], seite: teil}
            elif ereignis in ("gefuellt", "level", "geparkt", "ende"):
                teil[ereignis] = daten
                if ereignis == "gefuellt" and z["status"] in ("feuer", "bereit", "start"):
                    _status(z, "offen")
                if ereignis == "gefuellt" and seite == "master":
                    plan_open = True
                if ereignis == "ende" and seite == "slave" and (daten.get("wache") or {}).get("zu_ms"):
                    z["slave_zu_ms"] = int(daten["wache"]["zu_ms"])
                    db["slave_zu_ms"] = z["slave_zu_ms"]
                if ereignis == "ende":
                    beide = bool((z.get("master") or {}).get("ende")) and bool((z.get("slave") or {}).get("ende"))
                    if beide and z["status"] != "abbruch":
                        if z["status"] != "fehler":
                            _status(z, "fertig")
                        abrechnen = True
                _COND.notify_all()
                db.update({"status": z["status"], seite: teil})
            else:
                return jsonify({"ok": False, "msg": f"Ereignis '{ereignis}' unbekannt"}), 400
            sicht = _sicht(z)
        if db:
            _db(lid, db)
        if plan_open:
            klick = _zahl(daten.get("klick_ms"))

            def _offen():
                try:
                    ab = datetime.fromtimestamp(klick / 1000.0, tz=timezone.utc).isoformat() if klick else A["_wt_now_iso"]()
                    A["sb_update"]("trade_plans", {"id": f"eq.{z['plan_id']}", "status": "eq.planned"}, {"status": "open", "started_at": ab, "ended_at": None})
                except Exception as e:
                    print(f"[polar] ⚠️ Plan open {z['plan_id'][:8]}: {type(e).__name__}", flush=True)
            threading.Thread(target=_offen, daemon=True).start()
        if abrechnen:
            _abrechnen(z)
        return jsonify({"ok": True, **sicht})

    @app.route("/polar/stand", methods=["GET", "OPTIONS"])
    def polar_stand():
        """Tab (sb-token) oder Puls (X-Code-Token): Zustand eines Laufs bzw. der letzte Lauf eines Plans."""
        if request.method == "OPTIONS":
            return "", 200
        wer = A["_code_zugang"]()
        uid = wer[0] if wer else None
        if not uid:
            uid, err = A["_wd_login"]()
            if err:
                return err
        lid, pid = request.args.get("lauf_id") or "", request.args.get("plan_id") or ""
        z = _laden(lid) if lid else None
        if z is None and _uuid(pid):
            with _COND:
                z = next((x for x in sorted(_LAEUFE.values(), key=lambda x: x.get("angelegt_ms") or 0, reverse=True) if x["plan_id"] == pid), None)
            if z is None:
                try:
                    rows = A["sb_select"]("polar_lauf", {"select": "id", "plan_id": f"eq.{pid}", "order": "created_at.desc", "limit": "1"})
                    z = _laden(str(rows[0]["id"])) if rows else None
                except Exception:
                    z = None
        if not z:
            return jsonify({"ok": False, "msg": "kein Lauf"}), 404
        if str(uid) not in (z["master_uid"], z["slave_uid"]):
            err_a = True if wer else A["_admin_auth"]()[1]
            sicht = getattr(g, "admin_sicht", None)
            if err_a and not (sicht is not None and z["master_uid"] in sicht and z["slave_uid"] in sicht):
                return jsonify({"ok": False, "msg": "nicht deine Polar-Läufe"}), 403
        out = jsonify({"ok": True, **_sicht(z), "slave_live": _slave_live(z)})   # Live-P&L des Slaves (21.10.2026, Live-Ablauf)
        out.headers["Cache-Control"] = "no-store"
        return out

    # LIVE-ABLAUF (Finn 20.10.2026 ~23:55 Dubai, s. schritt_eintragen): der Bot meldet jede Phase je Seite. NUR der Prozess-Zustand — kein
    # eigener DB-Write (Prüfer S2 21.10.2026: ein später ankommender Schritt-Write hätte den gleichzeitigen melden-Write mit z. B. „ende" in
    # polar_lauf überschreiben können); die Schritte landen über die melden-Writes ({seite: teil}) mit in der DB. Nie ein Status-Wechsel, nie
    # ein Wecken der wartenden Verbindungen.
    @app.route("/polar/schritt", methods=["POST", "OPTIONS"])
    def polar_schritt():
        if request.method == "OPTIONS":
            return "", 200
        wer = A["_code_zugang"]()
        if not wer:
            return jsonify({"ok": False, "msg": "kein gültiger Schlüssel"}), 403
        d = request.get_json(silent=True) or {}
        lid, seite = str(d.get("lauf_id") or ""), str(d.get("seite") or "")
        z = _laden(lid)
        if not z or not _seite_ok(z, wer[0], seite):
            return jsonify({"ok": False, "msg": "Lauf/Seite passt nicht"}), 403
        with _COND:
            neu = schritt_eintragen(z.setdefault(seite, {}), d.get("phase"), d.get("text"), d.get("at_ms"))
        return jsonify({"ok": True, "neu": neu})

    # POLAR-VORRANG (20.10.2026, Finn: „Wenn Polar läuft, darf gar kein einziger Trade mehr gestartet werden … über die beteiligten IDs
    # keine Order, keine Balance-Lesung"): der Tab fragt hier alle 10 s, ob SEINE ID gerade in einem Polar-Lauf steckt (Master- ODER
    # Slave-Seite) — Bot-Läufe aus dem Prozess + polar_lauf und offene Hand-Polar-Pläne (gibt es mit und ohne POLAR_AUTO; ein Bot-Plan
    # wird erst beim Master-Fill open und nach dem Ende von _abrechnen auf review gesetzt — er zählt also nie als Hand-Plan). /polar/stand kennt nur
    # einen Lauf je lauf_id/plan_id, der Slave-Tab sieht den Plan der Master-ID nicht (RLS) — deshalb diese Liste (service role).
    # Takt: Tabs alle 30 s, Antwort 5 s im Prozess gecacht, EIN Select (Master 20.10.2026, Supabase-Diät).
    @app.route("/polar/aktiv", methods=["GET", "OPTIONS"])
    def polar_aktiv():
        if request.method == "OPTIONS":
            return "", 200
        wer = A["_code_zugang"]()
        uid = wer[0] if wer else None
        if not uid:
            uid, err = A["_wd_login"]()
            if err:
                return err
        uid = str(uid)
        jetzt = time.time()
        c = _AKTIV_CACHE.get(uid)
        if c and jetzt - c[0] < AKTIV_CACHE_S:       # 5 s je ID (workers 1 → ein Prozess, ein Cache)
            out = jsonify({"ok": True, "laeufe": c[1], "server_ms": _ms(), "cache": True})
            out.headers["Cache-Control"] = "no-store"
            return out
        with _COND:
            prozess = [dict(z) for z in _LAEUFE.values()]
        # EIN Select (Supabase-Diät): Polar-Pläne dieser ID (Master oder Slave), die noch planned/open sind, mit den zugehörigen
        # polar_lauf-Zeilen eingebettet (FK polar_lauf.plan_id → trade_plans.id, sql/2026-10-13_polar.sql). planned deckt die
        # Bereit-Phase des Bots (der Plan wird erst beim Fill open), open die Hand-Pläne und den laufenden Trade.
        try:
            rows = A["sb_select"]("trade_plans", {"select": "id,user_id,polar_slave_user_id,route,status,started_at,polar_lauf(id,status,created_at)",
                                                  "route": "eq.polar", "status": "in.(planned,open)",
                                                  "or": f"(user_id.eq.{uid},polar_slave_user_id.eq.{uid})",
                                                  "order": "created_at.desc", "limit": "20"}) or []
        except Exception as e:
            out = jsonify({"ok": False, "msg": f"Stand nicht lesbar: {type(e).__name__}", "laeufe": aktiv_liste(uid, prozess, [], [])})
            out.headers["Cache-Control"] = "no-store"
            return out, 503
        grenze = datetime.fromtimestamp(jetzt - AKTIV_FENSTER_H * 3600, timezone.utc).isoformat()
        db_laeufe = [l for l in laeufe_aus_plaenen(rows) if str(l.get("created_at") or "9") >= grenze]
        laeufe = aktiv_liste(uid, prozess, db_laeufe, rows)
        _AKTIV_CACHE[uid] = (jetzt, laeufe)
        if len(_AKTIV_CACHE) > 200:                  # nie wachsen lassen
            for k in [k for k, v in _AKTIV_CACHE.items() if jetzt - v[0] > 60]:
                _AKTIV_CACHE.pop(k, None)
        out = jsonify({"ok": True, "laeufe": laeufe, "server_ms": _ms()})
        out.headers["Cache-Control"] = "no-store"
        return out

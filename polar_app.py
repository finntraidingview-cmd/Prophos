"""POLAR — Railway-Taktgeber (13.10.2026, Finn). EIGENES MODUL, bewusst (Finn: „nur an neuen Sachen arbeiten, alten Code in Ruhe
lassen"): app.py bekommt nur `import polar_app; polar_app.registrieren(app, globals())` — alles andere steht hier.

Funded-Futures (Master, ID A, TradingView, PC A) gegen Funded-CFD (Slave, ID B, MT5, PC B) als Airbag statt Fusion-Live.
  /polar/plan    Popup legt den Plan im Namen der Master-ID an (service role; der Slave gehört einer ANDEREN ID)
  /polar/start   PC-Tab des Masters startet den Lauf → polar_lauf-Zeile + order_signale an die Slave-ID (aktion polar_slave)
  /polar/bereit  Puls meldet „steht vor dem Klick"; sind BEIDE bereit, gibt es EINE Feuerzeit (jetzt + Vorlauf)
  /polar/warte   wartende Verbindung (auf=feuer | zu) — Zustand im Prozess (gunicorn --workers 1 --threads 48); „Master zu" geht
                 ohne Datenbank-Umweg in Millisekunden an die wartende Slave-Verbindung
  /polar/melden  gefuellt / level / geparkt / zu / ende / abbruch / fehler
  /polar/stand   Anzeige (Tab) und Wiederaufnahme nach Railway-Neustart (Zustand aus polar_lauf)
  /polar/zeit    Uhrabgleich der Puls-Prozesse
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
ENDE = ("fertig", "abbruch", "fehler")
_LAEUFE = {}
_COND = threading.Condition()
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
    with _COND:
        return _LAEUFE.setdefault(lid, z)


def _sicht(z):
    return {"lauf_id": z["id"], "plan_id": z["plan_id"], "status": z["status"], "feuer_ms": z.get("feuer_ms"),
            "master_zu_ms": z.get("master_zu_ms"), "slave_zu_ms": z.get("slave_zu_ms"), "grund": z.get("grund"),
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
        Recht: Admin, die Master-ID selbst, oder eine Sicht, die beide IDs enthält."""
        if request.method == "OPTIONS":
            return "", 200
        _mail, err = A["_admin_auth"]()
        admin = err is None
        me = request.environ.get("prophos.admin_uid") if admin else None
        if not admin:
            me, err2 = A["_wd_login"]()
            if err2:
                return err2
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
        if not (admin or str(me) == mu or (sicht is not None and mu in sicht and su in sicht)):
            return jsonify({"ok": False, "msg": "keine Berechtigung für diese IDs"}), 403
        r = str(d.get("richtung") or "").lower()
        kt, lots = _zahl(d.get("kontrakte")), _zahl(d.get("lots"))
        sl_pkt, tp_pkt = _zahl(d.get("sl_pkt")), _zahl(d.get("tp_pkt"))
        if r not in ("buy", "sell") or not kt or kt <= 0 or not lots or lots <= 0 or not sl_pkt or not tp_pkt:
            return jsonify({"ok": False, "msg": "Richtung, Kontrakte, Lots und Level fehlen"}), 400
        if not _login_von_konto(s_acc):
            return jsonify({"ok": False, "msg": "Slave-Konto ohne MT5-Login (External ID oder Login fehlt)"}), 400
        zeile = {"user_id": mu, "master_account_id": m_acc["id"], "slave_account_id": s_acc["id"],
                 "master_name": m_acc.get("name"), "master_firm": m_acc.get("firm"), "slave_name": s_acc.get("name"), "slave_firm": s_acc.get("firm"),
                 "route": "polar", "status": "planned", "priority": "high", "richtung": r,
                 "master_symbol": str(d.get("symbol") or "").strip() or None, "master_contracts": kt, "master_risk": _zahl(d.get("master_risk")),
                 "slave_risk": _zahl(d.get("slave_risk")), "multiplier": round(lots / kt, 4),
                 "master_tp": _zahl(d.get("master_tp")), "master_sl": _zahl(d.get("master_sl")),
                 "polar_slave_user_id": su, "polar_pct": _zahl(d.get("polar_pct")) or 102.5,
                 "planned_for": datetime.now(timezone.utc).date().isoformat(),
                 "start_um": d.get("start_um") or A["_wt_now_iso"](),
                 "mt5_baseline": {"polar_auftrag": {"lots": lots, "sl_pkt": sl_pkt, "tp_pkt": tp_pkt, "kontrakte": kt,
                                                    "master_sl_pkt": _zahl(d.get("master_sl_pkt")), "master_tp_pkt": _zahl(d.get("master_tp_pkt"))}}}
        try:
            neu = A["sb_insert"]("trade_plans", zeile)
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Plan nicht angelegt: {str(e)[:200]}"}), 400
        return jsonify({"ok": True, "plan_id": str((neu or {}).get("id") or ""), "master_uid": mu, "slave_uid": su})

    @app.route("/polar/start", methods=["POST", "OPTIONS"])
    def polar_start():
        """PC-Tab der Master-ID: Lauf anlegen + Auftrag an die Slave-ID. Body {plan_id}."""
        if request.method == "OPTIONS":
            return "", 200
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
                return z.get("master_zu_ms") is not None
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
            if ereignis == "zu" and seite == "master":
                if z.get("master_zu_ms") is None:
                    z["master_zu_ms"] = _ms()
                    teil["zu"] = daten
                    if z["status"] not in ENDE:
                        _status(z, "master_zu")
                    else:
                        _COND.notify_all()
                    db = {"master_zu_ms": z["master_zu_ms"], "status": z["status"]}
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
        out = jsonify({"ok": True, **_sicht(z)})
        out.headers["Cache-Control"] = "no-store"
        return out

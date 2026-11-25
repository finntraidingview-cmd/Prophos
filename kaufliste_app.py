"""Kaufliste unter Accounts (KP2, 25.11.2026).

Finn 25.11.2026 (Demo demo/kaufplan.html abgenommen, „Design ganz nice“): unter Accounts direkt unter dem Muster-Portfolio eine Liste, eine Zeile
je zu kaufendem Konto, „Gekauft“ (echtes Bulk-Fenster mit Vorlage, nur External IDs einfügen), „Erledigt“ (weg, mit Rückgängig), Kästchen für
mehrere. Normale ID: nur eigene Zeilen. Admin: „Meine | Alle IDs“ und Anlegen für fremde IDs OHNE ID-Wechsel.

Rechnet nichts Neues: die Kaufzahl ist nachkauf.n des Vorrat-Laufs (app.py vorrat2_rechnen_lauf, seit KP2 mit Deckel „max. laufend“ je Firma
und FNF erst ab dem 1. erhaltenen FundedNext-Payout, vorrat_kauf_deckel), wie sie GET /admin/vorrat zeigt — also nach Abzug der seit dem Lauf
angelegten Konten und der offenen „bestellt“-Einträge (vorrat_bestellt, 48 h). „Erledigt“ = POST /admin/vorrat {aktion: 'bestellt'} (gibt es
seit 06.10.2026), Rückgängig = {aktion: 'bestellt_weg', id} — keine neue Tabelle.

Route:
  GET  /admin/kaufliste?alle=0|1     kompakte Zeilen je ID × Firma mit n > 0 (alle=1 nur Admin/Verwalter, Gate kapital_app._gate;
                                     sonst nur die eigene ID)
  POST /admin/kaufliste/spaeter      {user_id, firma, anzahl, tage 3|7|30} — KP2d „Später" (Finn: „ich will gerade nicht kaufen", z. B. weil die
                                     ID bald ins Live-Programm kommt): so viele Zeilen der Zelle tage lang ausblenden. Tabelle kaufliste_spaeter
                                     (sql/2026-11-25_kp2d_kaufliste_spaeter.sql) — OHNE Rechenwirkung (anders als vorrat_bestellt, das die
                                     Kaufzahl als „schon gekauft" senkt). Rückgängig: POST /admin/kaufliste/spaeter_weg {id}.
                                     Recht: eigene ID; fremde ID nur Admin/Verwalter seiner Gruppe (kapital_app._gate).
  „Firma pausieren" (Pfeil am Knopf) = vorhandene Sperr-Matrix POST /admin/vorrat {user_id, firma, status: 'pausiert'}; pausierte Zellen
  liefert GET mit (pausiert[]) zum Wieder-Freigeben.
Anlegen für eine FREMDE ID läuft über die vorhandene Route POST /admin/konto-anlegen (app.py, 29.10.2026: Service-Key, _admin_konto_gate,
Whitelist admin_konto_zeile, Doppel-Schutz, Max DD aus der Schablone, Kauf-Transaktion) — keine zweite Anlege-Route (Slave 5, PA1).
"""
import re
import time
from datetime import datetime, timedelta, timezone

from flask import request, jsonify

import kapital_app as K

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

_cache = {}
CACHE_S = 60                   # GET /admin/vorrat baut die ganze Admin-Basis — die Accounts-Seite fragt höchstens einmal je Minute neu

def zeilen_aus_vorrat(zellen, nur_uid=None, namen=None):
    """REIN RECHNEND (Selbsttest): Zellen von GET /admin/vorrat → Kauflisten-Zeilen (eine je ID × Firma mit n > 0).
    nur_uid: nur diese ID; namen: {user_id: Anzeigename} (people der Vorrat-Antwort). Sortierung wie die Demo: jetzt vor bald, Score, Name."""
    namen = namen or {}
    out = []
    for z in zellen or []:
        uid = str(z.get("user_id") or "")
        if nur_uid and uid != nur_uid:
            continue
        nk = z.get("nachkauf") or {}
        n = nk.get("n")
        if not isinstance(n, int) or n <= 0 or z.get("status") not in (None, "frei") or z.get("kauf_sperre"):
            continue
        if z.get("max_laufend") is None:     # Lauf noch ohne KP2-Deckel (Stand < 9, Neurechnung gescheitert) → lieber nichts als ungedeckelt (Review)
            continue
        out.append({
            "user_id": uid, "name": namen.get(uid) or z.get("user") or uid[:8], "firma": z.get("firma"), "n": n,
            "lage": nk.get("dringlichkeit") or z.get("lage"), "score": z.get("score"),
            "laufend": z.get("laufend_n"), "max": z.get("max_laufend"), "reserve": bool(z.get("reserve")),
            "pack": z.get("kauf_pack"),                     # Apex: 5er-Pack (Zeilen als Pack gruppiert, Gekauft/Erledigt fürs ganze Pack)
            "einheit": nk.get("einheit"), "preis_eur": nk.get("preis_eur"),
            "groesse": nk.get("groesse"),                   # KP3: Kauf-Größe des Unternehmens der ID (Emin 50k bei Futures) → Vorlage Firma × Größe
            "gruppe_ziel": bool(z.get("gruppe_id")),         # KP3: Zelle rechnet mit eigenen Gruppen-Zielen → Vorlage nur in genau dieser Größe
            "untergrenze": z.get("untergrenze"), "bestellt": z.get("bestellt"),
            "bestand": z.get("bestand_echt"),               # KP2g: Firmen-Kopf „Ist / Soll" (Ist = gesicherter Bestand, Soll = untergrenze)
        })
    rang = {"jetzt": 0, "bald": 1}
    out.sort(key=lambda x: (rang.get(x["lage"], 2), -(x["score"] or 0), str(x["name"]).lower(), str(x["firma"])))
    return out


def pausiert_aus_vorrat(zellen, nur_uid=None, namen=None):
    """REIN RECHNEND (Selbsttest): pausierte Zellen der Sperr-Matrix (status 'pausiert') → [{user_id, name, firma}] zum Wieder-Freigeben."""
    namen = namen or {}
    out = [{"user_id": str(z.get("user_id")), "name": namen.get(str(z.get("user_id"))) or str(z.get("user_id"))[:8], "firma": z.get("firma")}
           for z in zellen or [] if z.get("status") == "pausiert" and (not nur_uid or str(z.get("user_id")) == nur_uid)]
    return sorted(out, key=lambda x: (str(x["name"]).lower(), str(x["firma"])))


def gesperrt_aus_vorrat(zellen, nur_uid=None, namen=None):
    """REIN RECHNEND (Selbsttest), KP2k (Finn 26.11.2026): Zellen, die der Kauf-Deckel sperrt (kauf_sperre, z. B. FundedNext Futures
    „ab 1. FN-Payout") → [{user_id, name, firma, grund}]. Am Tacho grau + Chip statt 0 % wie eine normale Lücke."""
    namen = namen or {}
    out = [{"user_id": str(z.get("user_id")), "name": namen.get(str(z.get("user_id"))) or str(z.get("user_id"))[:8], "firma": z.get("firma"),
            "grund": str(z.get("kauf_sperre"))}
           for z in zellen or [] if z.get("kauf_sperre") and z.get("status") in (None, "frei")
           and (not nur_uid or str(z.get("user_id")) == nur_uid)]
    return sorted(out, key=lambda x: (str(x["name"]).lower(), str(x["firma"])))


SPAETER_TAGE = (3, 7, 30)
UUID = re.compile(r"^[0-9a-f-]{36}$")


def spaeter_pruefen(body):
    """REIN RECHNEND (Selbsttest): Body von POST /admin/kaufliste/spaeter → ((user_id, firma, anzahl, tage), None) oder (None, Fehler)."""
    b = body if isinstance(body, dict) else {}
    ziel = str(b.get("user_id") or "").strip().lower()
    firma = str(b.get("firma") or "").strip()[:80]
    anzahl, tage = b.get("anzahl"), b.get("tage", 7)
    if not UUID.match(ziel):
        return None, "user_id ungültig"
    if not firma:
        return None, "firma fehlt"
    if not isinstance(anzahl, int) or isinstance(anzahl, bool) or not 1 <= anzahl <= 20:
        return None, "anzahl muss 1–20 sein"
    if tage not in SPAETER_TAGE:
        return None, "tage muss 3, 7 oder 30 sein"
    return (ziel, firma, anzahl, tage), None


def _tabelle_fehlt(e):
    return getattr(getattr(e, "response", None), "status_code", 0) == 404


def registrieren(app, ns):
    A.update(ns)

    def spaeter_lesen(uids):
        """offene „Später"-Einträge (bis in der Zukunft, nicht zurückgenommen) der gegebenen IDs (None = alle). → (liste, bereit)"""
        try:
            rows = A["_sb_all"]("kaufliste_spaeter", {"select": "id,user_id,firma,anzahl,tage,bis,at", "weg_at": "is.null",
                                                      "bis": f"gt.{datetime.now(timezone.utc).isoformat()}", "order": "bis.asc"}) or []
        except Exception as e:
            if _tabelle_fehlt(e):
                return [], False
            raise
        return [dict(r, user_id=str(r.get("user_id"))) for r in rows if uids is None or str(r.get("user_id")) in uids], True

    def darf_ziel(uid, ziel):
        """eigene ID immer; fremde nur Admin (alle) bzw. Verwalter (Mitglied einer seiner Gruppen). → None oder Fehler-Antwort"""
        if ziel == str(uid):
            return None
        erlaubt, err = K._gate()
        if err:
            return err
        if erlaubt is None:
            return None
        rows = K._sb("GET", "id_gruppe_mitglied", {"select": "gruppe_id", "user_id": f"eq.{ziel}"}) or []
        if any(str(x.get("gruppe_id")) in erlaubt for x in rows):
            return None
        return jsonify({"ok": False, "error": "nur IDs der eigenen Gruppe"}), 403

    def _mit_spaeter(antwort, uid, admin):
        """„Später" bei JEDER Antwort frisch (kleine Tabelle, nicht im Merker) — sonst käme eine ausgeblendete Zeile nach Rückgängig erst nach 60 s."""
        try:
            sp, bereit = spaeter_lesen(None if admin else {str(uid)})
        except Exception as e:
            print(f"[kaufliste] ⚠️ Später nicht lesbar: {type(e).__name__}", flush=True)
            sp, bereit = [], False
        if admin:
            sichtbar = {z["user_id"] for z in antwort.get("zeilen") or []}
            sp = [x for x in sp if x["user_id"] in sichtbar]
        return dict(antwort, ich=str(uid), spaeter=sp, spaeter_bereit=bereit)

    @app.route("/admin/kaufliste/spaeter", methods=["POST", "OPTIONS"])
    def admin_kaufliste_spaeter():
        if request.method == "OPTIONS":
            return "", 200
        uid, err = A["_wd_login"]()
        if err:
            return err
        werte, fehler = spaeter_pruefen(request.get_json(silent=True))
        if fehler:
            return jsonify({"ok": False, "error": fehler}), 400
        ziel, firma, anzahl, tage = werte
        try:
            nein = darf_ziel(uid, ziel)
            if nein:
                return nein
            bis = (datetime.now(timezone.utc) + timedelta(days=tage)).isoformat()
            row = A["sb_insert"]("kaufliste_spaeter", {"user_id": ziel, "firma": firma, "anzahl": anzahl, "tage": tage, "bis": bis, "von": str(uid)})
        except Exception as e:
            if _tabelle_fehlt(e):
                return jsonify({"ok": False, "error": "SQL noch nicht eingespielt (sql/2026-11-25_kp2d_kaufliste_spaeter.sql)"}), 503
            print(f"[kaufliste] ⚠️ später: {type(e).__name__}", flush=True)
            return jsonify({"ok": False, "error": f"nicht gespeichert ({type(e).__name__})"}), 500
        return jsonify({"ok": True, "spaeter": {"id": row.get("id"), "user_id": ziel, "firma": firma, "anzahl": anzahl, "tage": tage, "bis": bis}})

    @app.route("/admin/kaufliste/spaeter_weg", methods=["POST", "OPTIONS"])
    def admin_kaufliste_spaeter_weg():
        if request.method == "OPTIONS":
            return "", 200
        uid, err = A["_wd_login"]()
        if err:
            return err
        sid = (request.get_json(silent=True) or {}).get("id")
        if not isinstance(sid, int) or isinstance(sid, bool):
            return jsonify({"ok": False, "error": "id fehlt"}), 400
        try:
            rows = K._sb("GET", "kaufliste_spaeter", {"select": "id,user_id", "id": f"eq.{sid}", "weg_at": "is.null"}) or []
            if not rows:
                return jsonify({"ok": False, "error": "nicht gefunden"}), 404
            nein = darf_ziel(uid, str(rows[0].get("user_id")))
            if nein:
                return nein
            K._sb("PATCH", "kaufliste_spaeter", {"id": f"eq.{sid}", "weg_at": "is.null"}, {"weg_at": datetime.now(timezone.utc).isoformat()})
        except Exception as e:
            if _tabelle_fehlt(e):
                return jsonify({"ok": False, "error": "SQL noch nicht eingespielt"}), 503
            return jsonify({"ok": False, "error": f"nicht zurückgenommen ({type(e).__name__})"}), 500
        return jsonify({"ok": True, "id": sid})

    @app.route("/admin/kaufliste", methods=["GET", "OPTIONS"])
    def admin_kaufliste():
        """Kauflisten-Zeilen. ?alle=1 nur für Admin/Verwalter (Gate wie Kapital) — sonst nur die eigene ID, auch für HT-IDs ohne
        admin_zugang-Zeile (die sehen in /admin/vorrat alle Zellen, hier bewusst nicht)."""
        if request.method == "OPTIONS":
            return "", 200
        uid, err = A["_wd_login"]()
        if err:
            return err
        alle = request.args.get("alle") == "1"
        admin = False
        if alle:
            erlaubt, gerr = K._gate()
            if gerr:
                return gerr
            admin = True
        schl = ("alle" if admin else uid, A["_admin_nur_uid"](), tuple(sorted(A["_admin_sicht"]() or ())))
        c = _cache.get(schl)
        # frisch=1 (nach Erledigt/Anlegen) umgeht den Merker höchstens alle 5 s — jede Antwort baut die ganze Admin-Basis (Review: Last)
        if c and (time.time() - c[0] < 5 or (time.time() - c[0] < CACHE_S and request.args.get("frisch") != "1")):
            return jsonify(_mit_spaeter(c[1], uid, admin))
        try:
            antwort_v = A["_vorrat_antwort"](A["admin_build_vorrat"]())
            zellen = antwort_v.get("zellen") or []
            namen = {str(p.get("user_id")): p.get("name") for p in antwort_v.get("people") or []}
            zeilen = zeilen_aus_vorrat(zellen, None if admin else str(uid), namen)
            antwort = {"ok": True, "alle": admin, "zeilen": zeilen, "n": sum(z["n"] for z in zeilen),
                       "pausiert": pausiert_aus_vorrat(zellen, None if admin else str(uid), namen),
                       "gesperrt": gesperrt_aus_vorrat(zellen, None if admin else str(uid), namen),
                       "lauf_at": antwort_v.get("gerechnet_um"),
                       "naechster_lauf": antwort_v.get("naechster_lauf")}
            _cache[schl] = (time.time(), antwort)
            return jsonify(_mit_spaeter(antwort, uid, admin))
        except Exception as e:
            print(f"[kaufliste] ⚠️ GET: {type(e).__name__}: {e}", flush=True)
            return jsonify({"ok": False, "error": f"Kaufliste nicht ladbar ({type(e).__name__})"}), 500

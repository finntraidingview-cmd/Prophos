"""Bankkonten je ID — Admin → Finanzen → Bankkonto (BK1, 24.11.2026).

Finn 24.11.2026: „… auch deren Bankkonto-Balance checken: indem ich dort immer manuell Transaktionen hinzufügen kann und von jeder ID
auch die IBAN sehe … Admin, neuer Reiter Finanzen, unterteilt in Meta Wallet und Bankkonto. Bei Bankkonto das Ganze immer manuell
eintragen.“

  bank_konten    je ID beliebig viele Konten (Zweck Account-Kauf / Vergütung / Sonstiges), mit IBAN
  bank_buchungen Hand-Buchungen (+ Eingang / − Ausgang); Saldo = start_saldo + Σ betrag

Eigenes Modul wie kapital_app.py; app.py hängt es nur an. Tabellen haben RLS ohne Policy für Logins → alles über den Service-Key hier.
Gate = kapital_app._gate (Finn + Pascal = alle Gruppen, Verwalter = nur seine Gruppe, jeder andere Login 403).

IBANs sind sensibel (Master 24.11.2026): nie in einer URL (Schreiben nur per JSON-Body, Lesen nur über GET ohne IBAN-Parameter),
nie in einem Log und nie in einer Fehlerantwort — PostgREST-Fehler enthalten bei Check-Verletzungen die ganze Zeile („Failing row
contains …“), darum gehen hier nur feste Texte bzw. der Fehlertyp raus.
"""
import re

from flask import request, jsonify

import kapital_app as K

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

ZWECKE = ("Account-Kauf", "Vergütung", "Sonstiges")
ARTEN = ("Einzahlung HT", "Account-Kauf", "Payout", "Gebühr", "Vergütung", "Sonstiges")
WAEHRUNGEN = ("EUR", "USD")


def _txt(v, n):
    s = str(v or "").strip()
    return s[:n] or None


def iban_normal(v):
    """IBAN ohne Leerzeichen, groß. Leer → None. Ungültige Form → '' (Aufrufer meldet 400). Prüfziffer nach ISO 13616 (mod 97)."""
    s = re.sub(r"\s+", "", str(v or "")).upper()
    if not s:
        return None
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return ""
    zahl = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return s if int(zahl) % 97 == 1 else ""


def saldo_rechnen(konten, buchungen):
    """Rein rechnend (Selbsttest): je Konto saldo = start_saldo + Σ betrag, anzahl, letzte (Datum). → {konto_id: {...}}."""
    out = {str(k["id"]): {"saldo": round(K._num(k.get("start_saldo")), 2), "anzahl": 0, "letzte": None} for k in konten}
    for b in buchungen:
        o = out.get(str(b.get("konto_id")))
        if o is None:
            continue
        o["saldo"] = round(o["saldo"] + K._num(b.get("betrag")), 2)
        o["anzahl"] += 1
        d = str(b.get("datum") or "")
        if d and (o["letzte"] is None or d > o["letzte"]):
            o["letzte"] = d
    return out


def _gruppen(erlaubt):
    return [{"id": str(x["id"]), "name": x.get("name") or "", "ht": not x.get("verwalter_user_id")}
            for x in (K._sb("GET", "id_gruppen", {"select": "id,name,verwalter_user_id", "order": "name.asc"}) or [])
            if K._darf(erlaubt, str(x["id"]))]


def _gruppe_waehlen(gruppen, wunsch):
    """Gewünschte Gruppe, wenn erlaubt; sonst HT (Finns Standard-Sicht), sonst die erste erlaubte (Verwalter: seine)."""
    if wunsch and any(x["id"] == wunsch for x in gruppen):
        return wunsch
    return next((x["id"] for x in gruppen if x["ht"]), gruppen[0]["id"] if gruppen else "")


def _mitglieder(gid):
    return {str(x["user_id"]) for x in (A["_sb_all"]("id_gruppe_mitglied", {"select": "user_id", "gruppe_id": f"eq.{gid}"}) or [])}


def _uid_gruppe(uid):
    rows = K._sb("GET", "id_gruppe_mitglied", {"select": "gruppe_id", "user_id": f"eq.{uid}"}) or []
    return str(rows[0]["gruppe_id"]) if rows else ""


def _konto_erlaubt(konto_id, erlaubt):
    """→ Konto-Zeile (id, user_id), wenn das Konto einer ID in einer erlaubten Gruppe gehört; sonst None."""
    rows = K._sb("GET", "bank_konten", {"select": "id,user_id", "id": f"eq.{konto_id}"}) or []
    if not rows:
        return None
    return rows[0] if K._darf(erlaubt, _uid_gruppe(rows[0]["user_id"])) else None


def _namen():
    try:
        r = A["_auth_liste_anfrage"]()
        out = {}
        for u in (r.json() or {}).get("users", []):
            mail = str(u.get("email") or "")
            meta = str((u.get("user_metadata") or {}).get("name") or "").strip()
            out[str(u.get("id"))] = meta or (mail.split("@")[0] if "@" in mail else "")
        return out
    except Exception:
        return {}


def _konto_felder(body, neu):
    """Felder für Anlegen/Ändern prüfen. neu=True: user_id Pflicht. → (dict, fehler)."""
    f = {}
    if "zweck" in body or neu:
        z = str(body.get("zweck") or "Account-Kauf").strip()
        if z not in ZWECKE:
            return None, "zweck: Account-Kauf, Vergütung oder Sonstiges"
        f["zweck"] = z
    if "waehrung" in body or neu:
        w = str(body.get("waehrung") or "EUR").upper()
        if w not in WAEHRUNGEN:
            return None, "waehrung EUR oder USD"
        f["waehrung"] = w
    if "iban" in body:
        i = iban_normal(body.get("iban"))
        if i == "":
            return None, "IBAN ungültig (Prüfziffer passt nicht) — bitte nochmal abschreiben"
        f["iban"] = i
    if "bic" in body:
        f["bic"] = re.sub(r"\s+", "", str(body.get("bic") or "")).upper()[:11] or None   # erst Leerzeichen weg, dann kürzen (Review)
    for k, n in (("bank", 80), ("inhaber", 120), ("notiz", 300)):
        if k in body:
            f[k] = _txt(body.get(k), n)
    if "start_saldo" in body:
        f["start_saldo"] = round(K._num(body.get("start_saldo")), 2)
    if "start_am" in body:
        v = str(body.get("start_am") or "").strip()
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return None, "start_am JJJJ-MM-TT"
        f["start_am"] = v or None
    if "aktiv" in body:
        f["aktiv"] = bool(body.get("aktiv"))
    return f, None


def _buchung_felder(body, neu):
    f = {}
    if "betrag" in body or neu:
        b = round(K._num(body.get("betrag")), 2)
        if b == 0:
            return None, "Betrag ≠ 0 (+ Eingang / − Ausgang)"
        f["betrag"] = b
    if "datum" in body or neu:
        d = K._datum(body.get("datum"))
        if not d:
            return None, "Datum JJJJ-MM-TT"
        f["datum"] = d
    if "art" in body or neu:
        a = str(body.get("art") or "Sonstiges").strip()
        if a not in ARTEN:
            return None, "Art unbekannt"
        f["art"] = a
    if "text" in body:
        f["text"] = _txt(body.get("text"), 300)
    return f, None


def _fehler(wo, e):
    # nur der Typ — nie der Text (kann Zeilenwerte inkl. IBAN tragen)
    print(f"[bank] ⚠️ {wo}: {type(e).__name__}", flush=True)
    return jsonify({"ok": False, "error": f"Speichern/Lesen fehlgeschlagen ({type(e).__name__})"}), 502


def registrieren(app, ns):
    A.update(ns)

    @app.route("/admin/bank", methods=["GET", "OPTIONS"])
    def admin_bank():
        """Konten + Buchungen der IDs EINER Gruppe (?gruppe=, sonst HT bzw. die des Verwalters) mit Saldo je Konto."""
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        try:
            gruppen = _gruppen(erlaubt)
            gid = _gruppe_waehlen(gruppen, K._uuid(request.args.get("gruppe")))
            if not gid:
                return jsonify({"ok": False, "error": "Keine Gruppe freigegeben"}), 403
            uids = _mitglieder(gid)
            konten = A["_sb_all"]("bank_konten", {"select": "*", "user_id": K._in(uids), "order": "created_at.asc,id.asc"}) if uids else []
            ids = [str(k["id"]) for k in konten]
            buchungen = A["_sb_all"]("bank_buchungen", {"select": "id,konto_id,datum,betrag,text,art,quelle,created_at",
                                                        "konto_id": K._in(ids), "order": "datum.asc,created_at.asc,id.asc"}) if ids else []
            s = saldo_rechnen(konten, buchungen)
            namen = _namen()
            for k in konten:
                k.update(s.get(str(k["id"])) or {})
                k["name"] = namen.get(str(k["user_id"])) or str(k["user_id"])[:8]
            personen = sorted(({"user_id": u, "name": namen.get(u) or u[:8]} for u in uids), key=lambda p: p["name"].lower())
        except Exception as e:
            return _fehler("GET", e)
        return jsonify({"ok": True, "gruppe": next(x for x in gruppen if x["id"] == gid), "gruppen": gruppen,
                        "personen": personen, "konten": konten, "buchungen": buchungen})

    @app.route("/admin/bank/konto", methods=["POST", "PATCH", "DELETE", "OPTIONS"])
    def admin_bank_konto():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "POST":
                uid = K._uuid(body.get("user_id"))
                if not uid or not K._darf(erlaubt, _uid_gruppe(uid)) or not _uid_gruppe(uid):
                    return jsonify({"ok": False, "error": "ID nicht freigegeben"}), 403
                f, fehler = _konto_felder(body, True)
                if fehler:
                    return jsonify({"ok": False, "error": fehler}), 400
                neu = A["sb_insert"]("bank_konten", dict(f, user_id=uid, angelegt_von=K._admin_uid() or None))
                return jsonify({"ok": True, "konto": neu})
            kid = K._uuid(body.get("id"))
            if not kid or not _konto_erlaubt(kid, erlaubt):
                return jsonify({"ok": False, "error": "Konto nicht gefunden"}), 404
            if request.method == "DELETE":
                K._sb("DELETE", "bank_konten", {"id": f"eq.{kid}"})        # Buchungen gehen per on delete cascade mit
                return jsonify({"ok": True})
            f, fehler = _konto_felder(body, False)
            if fehler:
                return jsonify({"ok": False, "error": fehler}), 400
            if not f:
                return jsonify({"ok": False, "error": "nichts zu ändern"}), 400
            geaendert = A["sb_update"]("bank_konten", {"id": f"eq.{kid}"}, f) or []
            return jsonify({"ok": True, "konto": geaendert[0] if geaendert else None})
        except Exception as e:
            return _fehler("konto " + request.method, e)

    @app.route("/admin/bank/buchung", methods=["POST", "PATCH", "DELETE", "OPTIONS"])
    def admin_bank_buchung():
        if request.method == "OPTIONS":
            return "", 200
        erlaubt, err = K._gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "POST":
                kid = K._uuid(body.get("konto_id"))
                if not kid or not _konto_erlaubt(kid, erlaubt):
                    return jsonify({"ok": False, "error": "Konto nicht gefunden"}), 404
                f, fehler = _buchung_felder(body, True)
                if fehler:
                    return jsonify({"ok": False, "error": fehler}), 400
                neu = A["sb_insert"]("bank_buchungen", dict(f, konto_id=kid, quelle="hand", angelegt_von=K._admin_uid() or None))
                return jsonify({"ok": True, "buchung": neu})
            bid = K._uuid(body.get("id"))
            rows = (K._sb("GET", "bank_buchungen", {"select": "id,konto_id", "id": f"eq.{bid}"}) or []) if bid else []
            if not rows or not _konto_erlaubt(rows[0]["konto_id"], erlaubt):
                return jsonify({"ok": False, "error": "Buchung nicht gefunden"}), 404
            if request.method == "DELETE":
                K._sb("DELETE", "bank_buchungen", {"id": f"eq.{bid}"})
                return jsonify({"ok": True})
            f, fehler = _buchung_felder(body, False)
            if fehler:
                return jsonify({"ok": False, "error": fehler}), 400
            if not f:
                return jsonify({"ok": False, "error": "nichts zu ändern"}), 400
            geaendert = A["sb_update"]("bank_buchungen", {"id": f"eq.{bid}"}, f) or []
            return jsonify({"ok": True, "buchung": geaendert[0] if geaendert else None})
        except Exception as e:
            return _fehler("buchung " + request.method, e)

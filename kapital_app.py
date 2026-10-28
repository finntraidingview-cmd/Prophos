"""KAPITAL IM SYSTEM je Gruppe (29.10.2026, Finn: 50 % an der Emin-Gruppe, legt demnächst weitere 5.000 $ nach und will eine Zahl, die
zeigt, ob Geld abgezweigt wird). EIGENES MODUL wie polar_app/support_app: app.py bekommt nur `kapital_app.registrieren(app, globals())`.

Finns Logik: jedes Prop-Konto ist auf Fusion gegengehedgt, also bleibt das Kapital im System nahezu gleich — blowt ein Konto, gewinnt der
Hedge ungefähr dessen Wert; besteht es, steckt das Geld im Konto und wird zum Payout. Weniger wird es nur durch Reibung. Fällt die Zahl
deutlich stärker als die Reibung, fehlt Geld. Gerechnet in US-Dollar (Finn 29.10.2026), Konten-Kosten (€) ÷ Prophos-Kurs.

  Ist  = Wallets der Gruppe (letzter wallet_snapshots-Tag je Wallet, inkl. Kasse 0xc27c… seit 29.10.2026)
         + Fusion-Balance (von Hand, kapital_fusion — Prophos liest Fusion nicht live)
         + Σ Gesamtkosten der laufenden Ketten, Boden 0 (= Accounts-Kachel „Gesamtwert", sql kapital_ketten)
         + offene Payouts (pending_payouts pending — in kapital_ketten wie empfangene vom Konto abgezogen, sonst doppelt)
  Soll = Σ Einlagen (kapital_einlagen) − Reibung (beendete Ketten, deren Kosten der Hedge nicht zurückgeholt hat)
         + Gewinne (beendete Ketten im Plus + laufende Ketten im Plus) − Krypto-Reibung (Gebühren + Swap-Saldo) − Ausschüttungen
  Abweichung = Ist − Soll. Rechnerisch bleibt darin nur, was keine Kategorie erklärt: Abflüsse ohne Account-Kauf/Fusion/Gebühr/Swap/
  internen Transfer, dazu Kurs- und CoinPayments-Aufschläge und fehlende Einlagen. Toleranz = max(250 $, 3 % der Account-Käufe).

Bewertung von Finn bestätigt (29.10.2026): laufendes Konto = Gesamtkosten (Kauf + Hedge der Kette − Payouts, Boden 0); Funded genauso,
im Plus zählt 0 und der Überschuss geht als Gewinn in die Soll-Linie. Reine Finanzübersicht — keine Regel-, Compliance- oder Risiko-Prüfung.

  GET    /admin/kapital?gruppe=<id>     Zahl, Aufschlüsselung, Verlauf, Abflüsse ohne Erklärung, Zuflüsse ohne Erklärung, Einlagen
  POST   /admin/kapital/einlage         {gruppe, betrag_usd, datum, ziel_wallet?, notiz?, quelle_tx?}
  DELETE /admin/kapital/einlage         {id}
  POST   /admin/kapital/fusion          {gruppe, betrag, waehrung EUR|USD, stand_am?, notiz?}

Rechte wie Liquide/Kunden-Zahlungen (_lq_gate): eingeloggt, ADMIN_EMAILS und NICHT eingeschränkt — ein Verwalter (Emin) sieht die Karte
nicht, sie ist Finns Kontrolle über die Gruppe. Tageswerte: jeder GET schreibt den heutigen Stand, dazu auf Railway ein Stunden-Takt."""
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import request, jsonify

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

STABLES = {"USDT", "USDC", "USDT0", "USDC.E"}      # nur echte Stable-Contracts landen so in wallet_tx (Kasse-Reiter blendet fremde Token aus)
MIN_BETRAG = 1.0                                    # darunter: Null-/Staub-Transfers (Address-Poisoning schickt 0-Beträge)
# Kategorien aus wallet_tx_kategorien, die einen Abfluss erklären (Finn: „Account-Kauf, Fusion, Gebühr oder interner Transfer")
ERKLAERT_RAUS = {"Account Kauf", "Account-Kauf", "Fusion Deposit", "Gebühr", "Gebühren / Gas", "Swap", "Umbuchung intern",
                 "Interner Transfer (Krypto)"}
# Geld, das die Gruppe bewusst verlässt (verteilt) — erklärt, aber auf der Soll-Seite abgezogen und eigens gezeigt
AUSSCHUETTUNG = {"Profit Split", "Interner Transfer auf Bank", "Kunden-Payout → Bank", "Auszahlung an Person", "Privat"}
ERKLAERT_REIN = {"Payout", "Payout Prop-Firm", "Swap", "Fusion Deposit", "Interner Transfer (Krypto)", "Umbuchung intern",
                 "Account Kauf", "Account-Kauf"}
TOLERANZ_MIN = 250.0
TOLERANZ_ANTEIL = 0.03         # Kurs-/CoinPayments-Aufschläge auf die Account-Käufe
TAKT_S = 3600
TZ_TAG = "Asia/Dubai"          # Tageswert nach Finns Tag

_takt = {"at": 0.0, "fehler": "", "laeuft": False}


def _sb(methode, tabelle, params=None, body=None, prefer=None, timeout=15):
    r = A["_sb_anfrage"](methode, f"{A['SUPABASE_URL']}/rest/v1/{tabelle}", params=params or {}, json=body,
                         headers=A["_sb_headers"](prefer), timeout=timeout)
    A["_sb_pruefen"](r)
    try:
        return r.json()
    except ValueError:
        return None


def _heute():
    if ZoneInfo:
        return datetime.now(ZoneInfo(TZ_TAG)).date()
    return (datetime.now(timezone.utc) + timedelta(hours=4)).date()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _in(menge):
    return "in.(" + ",".join(sorted(str(u) for u in menge)) + ")"


def _uuid(s):
    s = str(s or "").strip()
    return s if re.fullmatch(r"[0-9a-fA-F-]{36}", s) else ""


def _lookalike(a, b):
    """REIN RECHNEND: sieht Adresse a wie b aus, ohne b zu sein? Address-Poisoning kopiert Anfang + Ende (0x1B94…26e1)."""
    a, b = str(a or "").lower(), str(b or "").lower()
    return bool(a and b and a != b and len(a) > 12 and a[:6] == b[:6] and a[-4:] == b[-4:])


def bilanz_rechnen(ketten, snaps, fusion, einlagen, tx, labels, gruppen_adressen, fx, offene=None):
    """REIN RECHNEND (ohne DB, Selbsttest-fähig): alle Teile der Zahl aus den gelesenen Zeilen.
    ketten: kapital_ketten-Zeilen (gk_eur, archiviert, kauf_eur …) · snaps: {wallet_id: {usd, tag}} · fusion: jüngste kapital_fusion-Zeile
    oder None · einlagen: kapital_einlagen-Zeilen · tx: wallet_tx der Gruppen-Wallets · labels: {adresse_klein: kind}
    gruppen_adressen: set der eigenen Adressen (klein) · fx: € je $ · offene: pending_payouts-Zeilen (amount, currency)."""
    fx = fx if fx and 0.5 < fx < 1.5 else 0.85
    usd = lambda eur: eur / fx

    # ── Konten (Ketten) ──
    lauf = [k for k in ketten if not k.get("archiviert")]
    ende = [k for k in ketten if k.get("archiviert")]
    konten_eur = sum(max(0.0, _num(k.get("gk_eur"))) for k in lauf)
    plus_lauf_eur = sum(max(0.0, -_num(k.get("gk_eur"))) for k in lauf)
    reibung_eur = sum(max(0.0, _num(k.get("gk_eur"))) for k in ende)
    gewinn_ende_eur = sum(max(0.0, -_num(k.get("gk_eur"))) for k in ende)
    kauf_eur = sum(_num(k.get("kauf_eur")) for k in ketten)

    # ── Wallets ──
    wallets_usd = sum(_num(s.get("usd")) for s in snaps.values())
    wallets_tag = max((s.get("tag") or "" for s in snaps.values()), default="") or None

    # ── Fusion (von Hand) ──
    fus = None
    if fusion:
        b = _num(fusion.get("betrag"))
        w = (fusion.get("waehrung") or "EUR").upper()
        fus = {"betrag_usd": round(b / fx if w == "EUR" else b, 2), "betrag": b, "waehrung": w,
               "stand_am": fusion.get("stand_am"), "notiz": fusion.get("notiz") or ""}

    # ── Offene Payouts (beantragt, noch nicht da) — kapital_ketten zieht sie schon vom Konto ab ──
    offen_usd = sum(_num(o.get("amount")) / (fx if (o.get("currency") or "EUR").upper() != "USD" else 1.0) for o in (offene or []))

    # ── Wallet-Transfers: Gebühren, Swaps, Ausschüttungen, Abflüsse/Zuflüsse ohne Erklärung ──
    gebuehren = swap_raus = swap_rein = ausschuett = 0.0
    abfl, zufl = [], []
    gef = {"null": 0, "fake": 0, "poisoning": 0}
    bekannte = set(gruppen_adressen)
    for t in tx:
        if (t.get("kategorie") or "") in (ERKLAERT_RAUS | ERKLAERT_REIN | AUSSCHUETTUNG):
            bekannte.add(str(t.get("other") or "").lower())
    eingebucht = {str(e.get("quelle_tx")) for e in einlagen if e.get("quelle_tx")}
    for t in tx:
        sym = str(t.get("sym") or "").upper()
        betrag = _num(t.get("amount"))
        other = str(t.get("other") or "").lower()
        kat = t.get("kategorie") or ""
        if sym not in STABLES:
            gef["fake"] += 1
            continue
        if betrag < MIN_BETRAG:
            gef["null"] += 1
            continue
        if other not in bekannte and any(_lookalike(other, b) for b in bekannte):
            gef["poisoning"] += 1
            continue
        if other in gruppen_adressen:
            continue                                  # innerhalb der Gruppe (Emin → Kasse usw.) — bleibt im System
        raus = t.get("dir") == "raus"
        if kat == "Gebühr" or kat == "Gebühren / Gas":
            gebuehren += betrag if raus else -betrag
            continue
        if kat == "Swap":
            if raus:
                swap_raus += betrag
            else:
                swap_rein += betrag
            continue
        if kat in AUSSCHUETTUNG and raus:
            ausschuett += betrag
            continue
        zeile = {"key": t.get("tx_key"), "ts": t.get("ts"), "betrag": round(betrag, 2), "sym": sym, "an": t.get("other"),
                 "person": t.get("person_name"), "chain": t.get("chain"), "hash": t.get("hash"), "kategorie": kat,
                 "label": labels.get(other) or "", "kommentar": t.get("kommentar") or ""}
        if raus:
            if kat in ERKLAERT_RAUS or labels.get(other) == "coinpayments_deposit":
                continue
            abfl.append(zeile)
        else:
            if kat in ERKLAERT_REIN or labels.get(other) == "coinpayments_hot" or t.get("tx_key") in eingebucht:
                continue
            zufl.append(zeile)
    abfl.sort(key=lambda z: -z["betrag"])
    zufl.sort(key=lambda z: -z["betrag"])
    krypto_reibung = gebuehren + max(0.0, swap_raus - swap_rein)

    # ── Summen ──
    einlagen_usd = sum(_num(e.get("betrag_usd")) for e in einlagen)
    ist = wallets_usd + (fus["betrag_usd"] if fus else 0.0) + usd(konten_eur) + offen_usd
    soll = einlagen_usd - usd(reibung_eur) + usd(gewinn_ende_eur + plus_lauf_eur) - krypto_reibung - ausschuett
    abw = ist - soll
    toleranz = max(TOLERANZ_MIN, TOLERANZ_ANTEIL * usd(kauf_eur))
    r2 = lambda v: round(v, 2)
    return {
        "ist": {"summe": r2(ist), "wallets": r2(wallets_usd), "wallets_tag": wallets_tag, "wallets_n": len(snaps), "fusion": fus,
                "konten": r2(usd(konten_eur)), "konten_eur": r2(konten_eur), "konten_n": len(lauf),
                "konten_plus_n": sum(1 for k in lauf if _num(k.get("gk_eur")) < 0),
                "payouts_offen": r2(offen_usd), "payouts_offen_n": len(offene or [])},
        "soll": {"summe": r2(soll), "einlagen": r2(einlagen_usd), "einlagen_n": len(einlagen),
                 "reibung": r2(usd(reibung_eur)), "reibung_eur": r2(reibung_eur), "beendet_n": len(ende),
                 "gewinne": r2(usd(gewinn_ende_eur + plus_lauf_eur)), "gewinne_eur": r2(gewinn_ende_eur + plus_lauf_eur),
                 "krypto_reibung": r2(krypto_reibung), "gebuehren": r2(gebuehren), "swap_saldo": r2(swap_raus - swap_rein),
                 "ausschuettungen": r2(ausschuett)},
        "abweichung": r2(abw), "toleranz": r2(toleranz), "auffaellig": abs(abw) > toleranz,
        "kauf_usd": r2(usd(kauf_eur)), "fx": fx,
        "abfluesse": abfl[:200], "abfluesse_summe": r2(sum(z["betrag"] for z in abfl)), "abfluesse_n": len(abfl),
        "zufluesse": zufl[:200], "zufluesse_summe": r2(sum(z["betrag"] for z in zufl)), "zufluesse_n": len(zufl),
        "gefiltert": gef,
    }


def _gruppe_lesen(gid):
    rows = _sb("GET", "id_gruppen", {"select": "id,name,verwalter_user_id", "id": f"eq.{gid}"}) or []
    return rows[0] if rows else None


def _daten_lesen(gid):
    """Alle Zeilen für bilanz_rechnen. Fehler fliegen durch (Aufrufer antwortet 502)."""
    fx = A["_lq_fx"]()
    mit = [str(r["user_id"]) for r in (_sb("GET", "id_gruppe_mitglied", {"select": "user_id", "gruppe_id": f"eq.{gid}"}) or [])]
    r = A["_sb_anfrage"]("POST", f"{A['SUPABASE_URL']}/rest/v1/rpc/kapital_ketten", headers=A["_sb_headers"](), timeout=(5, 30),
                         json={"p_gruppe": gid, "p_fx": fx})
    A["_sb_pruefen"](r)
    ketten = r.json() or []
    wallets = A["_sb_all"]("id_wallets", {"select": "id,person_name,chain,address", "person_uid": _in(mit)}) if mit else []
    wids = [w["id"] for w in wallets]
    snaps = {}
    if wids:
        ab = (_heute() - timedelta(days=30)).isoformat()
        for s in A["_sb_all"]("wallet_snapshots", {"select": "id,wallet_id,day,usdt,coin_usdt", "wallet_id": _in(wids),
                                                    "day": f"gte.{ab}", "order": "day.desc,id.asc"}):
            if s["wallet_id"] not in snaps:            # jüngster Tag je Wallet
                snaps[s["wallet_id"]] = {"usd": _num(s.get("usdt")) + _num(s.get("coin_usdt")), "tag": s.get("day")}
    offene = _sb("GET", "pending_payouts", {"select": "amount,currency", "status": "eq.pending", "user_id": _in(mit)}) or [] if mit else []
    fus = _sb("GET", "kapital_fusion", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "created_at.desc", "limit": "1"}) or []
    einl = A["_sb_all"]("kapital_einlagen", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "datum.asc,id.asc"})
    tx = A["_sb_all"]("wallet_tx", {"select": "tx_key,wallet_id,chain,person_name,hash,ts,dir,amount,sym,other,kategorie,kommentar",
                                    "wallet_id": _in(wids), "order": "ts.desc,id.asc"}) if wids else []
    adressen = {str(w["address"]).lower() for w in wallets}
    others = sorted({str(t.get("other") or "").lower() for t in tx if t.get("other")})
    labels = {}
    for i in range(0, len(others), 150):               # URL-Länge: in Häppchen; wallet_labels speichert die Adresse klein
        for l in _sb("GET", "wallet_labels", {"select": "address,kind", "address": _in(others[i:i + 150])}) or []:
            labels[str(l["address"]).lower()] = l.get("kind") or ""
    return {"fx": fx, "ketten": ketten, "snaps": snaps, "fusion": fus[0] if fus else None, "einlagen": einl, "tx": tx,
            "labels": labels, "adressen": adressen, "wallets_n": len(wallets), "offene": offene}


def _tageswert_schreiben(gid, b):
    A["sb_upsert"]("kapital_tageswerte", {
        "gruppe_id": gid, "tag": _heute().isoformat(), "ist_usd": b["ist"]["summe"], "soll_usd": b["soll"]["summe"],
        "abweichung_usd": b["abweichung"], "updated_at": datetime.now(timezone.utc).isoformat(),
        "teile": {"ist": b["ist"], "soll": {k: v for k, v in b["soll"].items()}, "toleranz": b["toleranz"],
                  "abfluesse_summe": b["abfluesse_summe"], "abfluesse_n": b["abfluesse_n"], "fx": b["fx"]}})


def kapital_fuer(gid, schreiben=True):
    d = _daten_lesen(gid)
    b = bilanz_rechnen(d["ketten"], d["snaps"], d["fusion"], d["einlagen"], d["tx"], d["labels"], d["adressen"], d["fx"], d["offene"])
    b["ist"]["wallets_gesamt_n"] = d["wallets_n"]
    if schreiben:
        try:
            _tageswert_schreiben(gid, b)
        except Exception as e:
            print(f"[kapital] ⚠️ Tageswert: {type(e).__name__}: {e}", flush=True)
    b["einlagen"] = [{"id": e["id"], "betrag_usd": _num(e["betrag_usd"]), "datum": e.get("datum"), "ziel_wallet": e.get("ziel_wallet") or "",
                      "notiz": e.get("notiz") or "", "quelle_tx": e.get("quelle_tx") or ""} for e in d["einlagen"]]
    b["verlauf"] = [{"tag": r["tag"], "ist": _num(r["ist_usd"]), "soll": _num(r["soll_usd"]), "abw": _num(r["abweichung_usd"])}
                    for r in A["_sb_all"]("kapital_tageswerte", {"select": "tag,ist_usd,soll_usd,abweichung_usd",
                                                                  "gruppe_id": f"eq.{gid}", "order": "tag.asc"})]
    return b


def _takt_gruppen():
    """Gruppen mit Verwalter (heute Emin) — Hermann Technologies erst, wenn Finn es will."""
    return [str(g["id"]) for g in (_sb("GET", "id_gruppen", {"select": "id", "verwalter_user_id": "not.is.null"}) or [])]


def _takt_schleife():
    time.sleep(90)                                     # Start des Backends nicht belasten
    while True:
        _takt["laeuft"] = True
        try:
            for gid in _takt_gruppen():
                kapital_fuer(gid, schreiben=True)
            _takt["fehler"] = ""
        except Exception as e:
            _takt["fehler"] = f"{type(e).__name__}: {e}"
            print(f"[kapital] ⚠️ Takt: {_takt['fehler']}", flush=True)
        _takt["at"] = time.time()
        _takt["laeuft"] = False
        time.sleep(TAKT_S)


def _admin_uid():
    return str(request.environ.get("prophos.admin_uid") or "")


def registrieren(app, ns):
    """Routen an die Flask-App hängen; auf Railway den Stunden-Takt starten (auf den PCs ist PROPHOS_FRONTEND gesetzt — dort nie)."""
    A.update(ns)

    @app.route("/admin/kapital", methods=["GET", "OPTIONS"])
    def admin_kapital():
        if request.method == "OPTIONS":
            return "", 200
        err = A["_lq_gate"]()
        if err:
            return err
        try:
            gruppen = [{"id": str(g["id"]), "name": g.get("name") or "", "ht": not g.get("verwalter_user_id")}
                       for g in (_sb("GET", "id_gruppen", {"select": "id,name,verwalter_user_id", "order": "name.asc"}) or [])]
            gid = _uuid(request.args.get("gruppe"))
            if not gid:                                # Standard: erste Gruppe mit Verwalter (Emin)
                gid = next((g["id"] for g in gruppen if not g["ht"]), "")
            g = next((x for x in gruppen if x["id"] == gid), None)
            if not g:
                return jsonify({"ok": False, "error": "Gruppe nicht gefunden", "gruppen": gruppen}), 404
            b = kapital_fuer(gid, schreiben=True)
        except Exception as e:
            print(f"[kapital] ⚠️ GET: {type(e).__name__}: {e}", flush=True)
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502
        return jsonify(dict(b, ok=True, gruppe=g, gruppen=gruppen, takt={"fehler": _takt["fehler"]},
                            generated=datetime.now(timezone.utc).isoformat()))

    @app.route("/admin/kapital/einlage", methods=["POST", "DELETE", "OPTIONS"])
    def admin_kapital_einlage():
        if request.method == "OPTIONS":
            return "", 200
        err = A["_lq_gate"]()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "DELETE":
                eid = _uuid(body.get("id"))
                if not eid:
                    return jsonify({"ok": False, "error": "id nötig"}), 400
                weg = _sb("DELETE", "kapital_einlagen", {"id": f"eq.{eid}"}, prefer="return=representation") or []
                return jsonify({"ok": bool(weg)}) if weg else (jsonify({"ok": False, "error": "nicht gefunden"}), 404)
            gid = _uuid(body.get("gruppe"))
            betrag = _num(body.get("betrag_usd"))
            datum = str(body.get("datum") or "").strip() or _heute().isoformat()
            if not gid or not (betrag > 0) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
                return jsonify({"ok": False, "error": "gruppe, betrag_usd > 0 und datum (JJJJ-MM-TT) nötig"}), 400
            zeile = {"gruppe_id": gid, "betrag_usd": round(betrag, 2), "datum": datum,
                     "ziel_wallet": str(body.get("ziel_wallet") or "").strip()[:120] or None,
                     "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                     "quelle_tx": str(body.get("quelle_tx") or "").strip()[:200] or None, "angelegt_von": _admin_uid() or None}
            neu = A["sb_insert"]("kapital_einlagen", zeile)
            return jsonify({"ok": True, "einlage": neu})
        except requests.exceptions.HTTPError as e:
            txt = str(getattr(e.response, "text", "") or "")
            if "duplicate key" in txt or "23505" in txt:
                return jsonify({"ok": False, "error": "Dieser Zufluss ist schon als Einlage gebucht"}), 409
            return jsonify({"ok": False, "error": f"HTTPError: {txt[:200]}"}), 502
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    @app.route("/admin/kapital/fusion", methods=["POST", "OPTIONS"])
    def admin_kapital_fusion():
        if request.method == "OPTIONS":
            return "", 200
        err = A["_lq_gate"]()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        gid = _uuid(body.get("gruppe"))
        betrag = _num(body.get("betrag"))
        w = str(body.get("waehrung") or "EUR").upper()
        stand = str(body.get("stand_am") or "").strip() or _heute().isoformat()
        if not gid or betrag < 0 or w not in ("EUR", "USD") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stand):
            return jsonify({"ok": False, "error": "gruppe, betrag ≥ 0, waehrung EUR/USD und stand_am nötig"}), 400
        try:
            neu = A["sb_insert"]("kapital_fusion", {"gruppe_id": gid, "betrag": round(betrag, 2), "waehrung": w, "stand_am": stand,
                                                    "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                                                    "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "fusion": neu})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    if (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "").strip() \
            and not os.environ.get("PROPHOS_FRONTEND"):
        threading.Thread(target=_takt_schleife, name="kapital-takt", daemon=True).start()

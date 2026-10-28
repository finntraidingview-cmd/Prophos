"""KAPITAL IM SYSTEM je Gruppe (29.10.2026, Finn: 50 % an der Emin-Gruppe, legt demnächst weitere 5.000 $ nach und will eine Zahl, die
zeigt, ob Geld abgezweigt wird). EIGENES MODUL wie polar_app/support_app: app.py bekommt nur `kapital_app.registrieren(app, globals())`.

Finns Logik: jedes Prop-Konto ist auf Fusion gegengehedgt, also bleibt das Kapital im System nahezu gleich. Ein Konto zählt mit seinen
Gesamtkosten = Kauf + bisherige Hedge-Verluste (Finns Beispiel: Kauf 500 €, Blow → die 500 € kommen über den Hedge zurück; Bestehen →
Phase 2, im Konto stecken 1.000 € = 500 Kauf + 500 Hedge-Verlust, der auf Fusion fehlt). Die Summe sinkt nur durch Reibung; fällt sie
deutlich stärker, fehlt Geld.

ALLES IN EUR (Finn 29.10.2026, Nachtrag über die Vertrags-Session — ersetzt die erste Antwort „US-Dollar"): Wallets (USDT/USDC ≈ USD) zum
EZB-Tageskurs (frankfurter.dev, 6 h gemerkt; Rückfall Prophos-Kurs user_settings fx_usd_eur, sichtbar markiert), Fusion ist EUR,
Geschäftskonto in EUR. Account-Käufe zählen mit dem in Prophos gebuchten €-Betrag; dass on-chain in USDT bezahlt wurde, liegt als Kurs- und
CoinPayments-Abweichung in der Toleranz.

  Ist („insgesamt geparkt") = Wallets der Gruppe (letzter wallet_snapshots-Tag je Wallet, inkl. Kasse 0xc27c…)
         + Fusion (live aus mt5_live: Equity, je hedge_login nur einmal, Zeile ≤ 1 h alt; sonst Hand-Eingabe kapital_fusion)
         + Geschäftskonto (Σ kapital_gk_buchungen)
         + Σ Gesamtkosten der laufenden Ketten, Boden 0 (= Accounts-Kachel „Gesamtwert", sql kapital_ketten)
         + offene Payouts (pending_payouts pending — kapital_ketten zieht sie schon vom Konto ab, sonst doppelt)
  Soll = Σ Einlagen − Reibung (beendete Ketten, deren Kosten der Hedge nicht zurückgeholt hat — u. a. CFD-Blows, deren Hedge die Gebühr nur
         zu 64–88 % deckt) + Gewinne (Ketten im Plus) − Gebühren/Swap-Saldo − Ausschüttungen (wallet_tx Profit Split …)
         + Geschäftskonto-Buchungen außer „Umbuchung Krypto" (Kundenzahlung +, PC-Kauf/Ausgabe/Entnahme −)
  Abweichung = Ist − Soll, Toleranz max(250 €, 3 % der Account-Käufe). Reine Finanzübersicht — keine Regel-, Compliance- oder Risiko-Prüfung.

  GET    /admin/kapital?gruppe=<id>     Zahl, Aufschlüsselung, Fusion-Report, Geschäftskonto, Verlauf, Abflüsse/Zuflüsse ohne Erklärung
  POST   /admin/kapital/einlage         {gruppe, betrag, waehrung EUR|USD, datum, ziel_wallet?, notiz?, quelle_tx?}  · DELETE {id}
  POST   /admin/kapital/fusion          {gruppe, betrag, waehrung, stand_am?, notiz?}  (Rückfall, wenn mt5_live nicht frisch)
  POST   /admin/kapital/gk              {gruppe, datum, betrag (± ), waehrung, kategorie, text}  · DELETE {id}

Rechte wie die Admin-Übersicht (_gate, seit 29.10.2026 04:25): eingeloggt und im Admin NICHT eingeschränkt — Verwalter (Emin) und „nur
eigene“ bekommen 403. Bis dahin _lq_gate (ADMIN_EMAILS): „Finn + Pascal“ steht nicht in ADMIN_EMAILS und sah nur „Nur für Voll-Admins.“
Tageswerte: jeder GET schreibt den
heutigen Stand, dazu auf Railway ein Stunden-Takt."""
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import request, jsonify, g

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

STABLES = {"USDT", "USDC", "USDT0", "USDC.E"}      # nur echte Stable-Contracts landen so in wallet_tx (Kasse-Reiter blendet fremde Token aus)
MIN_BETRAG = 1.0                                    # darunter: Null-/Staub-Transfers (Address-Poisoning schickt 0-Beträge)
# Kategorien aus wallet_tx_kategorien, die einen Abfluss erklären (Finn: „Account-Kauf, Fusion, Gebühr oder interner Transfer"). „Interner
# Transfer auf Bank" ist seit dem Geschäftskonto intern (Gegenbuchung dort „Umbuchung Krypto").
ERKLAERT_RAUS = {"Account Kauf", "Account-Kauf", "Fusion Deposit", "Gebühr", "Gebühren / Gas", "Swap", "Umbuchung intern",
                 "Interner Transfer (Krypto)", "Interner Transfer auf Bank"}
# Geld, das die Gruppe bewusst verlässt (verteilt) — erklärt, aber auf der Soll-Seite abgezogen und eigens gezeigt
AUSSCHUETTUNG = {"Profit Split", "Kunden-Payout → Bank", "Auszahlung an Person", "Privat"}
ERKLAERT_REIN = {"Payout", "Payout Prop-Firm", "Swap", "Fusion Deposit", "Interner Transfer (Krypto)", "Interner Transfer auf Bank",
                 "Umbuchung intern", "Account Kauf", "Account-Kauf"}
GK_NEUTRAL = {"Umbuchung Krypto"}                   # Geschäftskonto ↔ Wallets: Tasche wechselt, Soll bleibt
GK_KATEGORIEN = ["Anfangsstand", "Kundenzahlung", "PC-Kauf", "Ausgabe", "Einlage", "Entnahme", "Umbuchung Krypto", "Sonstiges"]
TOLERANZ_MIN = 250.0
TOLERANZ_ANTEIL = 0.03         # Kurs-/CoinPayments-Aufschläge auf die Account-Käufe
FUSION_FRISCH_S = 3600         # mt5_live-Zeile älter → Hand-Eingabe
KURS_MERKEN_S = 6 * 3600
TAKT_S = 3600
TZ_TAG = "Asia/Dubai"          # Tageswert nach Finns Tag

_takt = {"at": 0.0, "fehler": "", "laeuft": False}
_kurs = {"bis": 0.0, "wert": None}


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


def _ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _lookalike(a, b):
    """REIN RECHNEND: sieht Adresse a wie b aus, ohne b zu sein? Address-Poisoning kopiert Anfang + Ende (0x1B94…26e1)."""
    a, b = str(a or "").lower(), str(b or "").lower()
    return bool(a and b and a != b and len(a) > 12 and a[:6] == b[:6] and a[-4:] == b[-4:])


def tageskurs():
    """{fx: € je $, quelle, stand} — EZB-Referenzkurs über frankfurter.dev (keyless, früher .app), 6 h gemerkt. Rückfall: Prophos-Kurs (Hand-Eingabe in
    den Einstellungen) mit Quelle „Prophos-Einstellung", damit die Karte zeigt, dass es kein Tageskurs ist."""
    jetzt = time.time()
    if _kurs["wert"] and _kurs["bis"] > jetzt:
        return _kurs["wert"]
    try:
        r = requests.get("https://api.frankfurter.dev/v1/latest", params={"from": "USD", "to": "EUR"}, timeout=6)
        r.raise_for_status()
        j = r.json()
        fx = float(j["rates"]["EUR"])
        if 0.5 < fx < 1.5:
            _kurs.update(bis=jetzt + KURS_MERKEN_S, wert={"fx": fx, "quelle": "EZB-Referenzkurs (frankfurter.dev)", "stand": j.get("date")})
            return _kurs["wert"]
    except Exception as e:
        print(f"[kapital] ⚠️ Tageskurs: {type(e).__name__}: {e}", flush=True)
    w = {"fx": A["_lq_fx"](), "quelle": "Prophos-Einstellung (kein Tageskurs erreichbar)", "stand": None}
    _kurs.update(bis=jetzt + 600, wert=w)                # Rückfall nur 10 min merken, dann wieder EZB versuchen
    return w


def fusion_live_waehlen(zeilen, logins, jetzt=None):
    """REIN RECHNEND: aus mt5_live-Zeilen je hedge_login die frischeste (mehrere PC-Instanzen schreiben dasselbe Konto), Equity vor Balance
    (offene Hedges stecken sonst doppelt drin oder fehlen), nur ≤ FUSION_FRISCH_S alt. → {eur_roh: {login: (betrag, waehrung)}, stand, logins}
    oder None, wenn kein Login frisch ist."""
    jetzt = jetzt or datetime.now(timezone.utc)
    best = {}
    for z in zeilen or []:
        lg = str(z.get("hedge_login") or "").strip()
        st = z.get("status") if isinstance(z.get("status"), dict) else {}
        t = _ts(z.get("updated_at"))
        if lg not in logins or t is None:
            continue
        wert = st.get("hedge_equity") if st.get("hedge_equity") not in (None, "") else st.get("hedge_balance")
        if wert in (None, ""):
            continue
        if lg not in best or t > best[lg][0]:
            best[lg] = (t, _num(wert), str(st.get("hedge_currency") or "EUR").upper(), st.get("hedge_equity") not in (None, ""))
    frisch = {lg: v for lg, v in best.items() if (jetzt - v[0]).total_seconds() <= FUSION_FRISCH_S}
    if not frisch:
        return None
    return {"konten": {lg: {"betrag": v[1], "waehrung": v[2], "equity": v[3], "stand": v[0].isoformat()} for lg, v in frisch.items()},
            "stand": min(v[0] for v in frisch.values()).isoformat()}


def bilanz_rechnen(ketten, snaps, fusion_live, fusion_hand, einlagen, tx, labels, gruppen_adressen, fx, offene=None, gk=None):
    """REIN RECHNEND (ohne DB, Selbsttest-fähig): alle Teile der Zahl in EUR.
    ketten: kapital_ketten-Zeilen (gk_eur, hedge_eur, archiviert, kauf_eur …) · snaps: {wallet_id: {usd, tag}} · fusion_live: Ergebnis von
    fusion_live_waehlen oder None · fusion_hand: jüngste kapital_fusion-Zeile oder None · einlagen: kapital_einlagen · tx: wallet_tx der
    Gruppen-Wallets · labels: {adresse_klein: kind} · gruppen_adressen: set der eigenen Adressen (klein) · fx: € je $ ·
    offene: pending_payouts (amount, currency) · gk: kapital_gk_buchungen (betrag, waehrung, kategorie)."""
    fx = fx if fx and 0.5 < fx < 1.5 else 0.85
    eur = lambda betrag, waehrung="USD": _num(betrag) * (fx if str(waehrung or "USD").upper() == "USD" else 1.0)
    r2 = lambda v: round(v, 2)

    # ── Konten (Ketten) ──
    lauf = [k for k in ketten if not k.get("archiviert")]
    ende = [k for k in ketten if k.get("archiviert")]
    konten = sum(max(0.0, _num(k.get("gk_eur"))) for k in lauf)
    plus_lauf = sum(max(0.0, -_num(k.get("gk_eur"))) for k in lauf)
    reibung = sum(max(0.0, _num(k.get("gk_eur"))) for k in ende)
    gewinn_ende = sum(max(0.0, -_num(k.get("gk_eur"))) for k in ende)
    kauf = sum(_num(k.get("kauf_eur")) for k in ketten)
    hedge_ergebnis = -sum(_num(k.get("hedge_eur")) for k in ketten)      # + = Fusion hat gewonnen

    # ── Wallets (USD-Stables + Coins in USDT bewertet) ──
    wallets_usd = sum(_num(s.get("usd")) for s in snaps.values())
    wallets_tag = max((s.get("tag") or "" for s in snaps.values()), default="") or None

    # ── Fusion: live vor Hand ──
    if fusion_live:
        fus_eur = sum(eur(v["betrag"], v["waehrung"]) for v in fusion_live["konten"].values())
        fus = {"eur": r2(fus_eur), "quelle": "live", "stand": fusion_live["stand"], "logins": sorted(fusion_live["konten"]),
               "equity": all(v.get("equity") for v in fusion_live["konten"].values())}
    elif fusion_hand:
        fus = {"eur": r2(eur(fusion_hand.get("betrag"), fusion_hand.get("waehrung") or "EUR")), "quelle": "hand",
               "stand": fusion_hand.get("stand_am"), "logins": [], "notiz": fusion_hand.get("notiz") or ""}
    else:
        fus = None

    # ── Offene Payouts (beantragt, noch nicht da) ──
    offen = sum(eur(o.get("amount"), o.get("currency") or "EUR") for o in (offene or []))

    # ── Geschäftskonto ──
    gk = gk or []
    gk_saldo = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk)
    gk_soll = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk if (b.get("kategorie") or "") not in GK_NEUTRAL)
    gk_rein = sum(eur(b.get("betrag"), b.get("waehrung") or "EUR") for b in gk
                  if (b.get("kategorie") or "") not in GK_NEUTRAL and _num(b.get("betrag")) > 0)

    # ── Wallet-Transfers: Gebühren, Swaps, Ausschüttungen, Fusion-Flüsse, Abflüsse/Zuflüsse ohne Erklärung (Beträge in USD) ──
    gebuehren = swap_raus = swap_rein = ausschuett = fus_ein = fus_aus = 0.0
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
        if kat in ("Gebühr", "Gebühren / Gas"):
            gebuehren += betrag if raus else -betrag
            continue
        if kat == "Swap":
            if raus:
                swap_raus += betrag
            else:
                swap_rein += betrag
            continue
        if kat == "Fusion Deposit":
            if raus:
                fus_ein += betrag
            else:
                fus_aus += betrag
            continue
        if kat in AUSSCHUETTUNG and raus:
            ausschuett += betrag
            continue
        zeile = {"key": t.get("tx_key"), "ts": t.get("ts"), "betrag": r2(betrag), "betrag_eur": r2(eur(betrag)), "sym": sym,
                 "an": t.get("other"), "person": t.get("person_name"), "chain": t.get("chain"), "hash": t.get("hash"), "kategorie": kat,
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
    krypto_reibung = eur(gebuehren + max(0.0, swap_raus - swap_rein))

    # ── Summen ──
    einlagen_eur = sum(eur(e.get("betrag"), e.get("waehrung") or "EUR") for e in einlagen)
    wallets = eur(wallets_usd)
    ist = wallets + (fus["eur"] if fus else 0.0) + gk_saldo + konten + offen
    soll = einlagen_eur - reibung + gewinn_ende + plus_lauf - krypto_reibung - eur(ausschuett) + gk_soll
    abw = ist - soll
    toleranz = max(TOLERANZ_MIN, TOLERANZ_ANTEIL * kauf)
    return {
        "ist": {"summe": r2(ist), "wallets": r2(wallets), "wallets_usd": r2(wallets_usd), "wallets_tag": wallets_tag,
                "wallets_n": len(snaps), "fusion": fus, "geschaeftskonto": r2(gk_saldo), "gk_n": len(gk),
                "konten": r2(konten), "konten_n": len(lauf), "konten_plus_n": sum(1 for k in lauf if _num(k.get("gk_eur")) < 0),
                "payouts_offen": r2(offen), "payouts_offen_n": len(offene or [])},
        "soll": {"summe": r2(soll), "einlagen": r2(einlagen_eur), "einlagen_n": len(einlagen),
                 "reibung": r2(reibung), "beendet_n": len(ende), "gewinne": r2(gewinn_ende + plus_lauf),
                 "krypto_reibung": r2(krypto_reibung), "gebuehren": r2(eur(gebuehren)), "swap_saldo": r2(eur(swap_raus - swap_rein)),
                 "ausschuettungen": r2(eur(ausschuett)), "geschaeftskonto": r2(gk_soll), "gk_einnahmen": r2(gk_rein),
                 "gk_ausgaben": r2(gk_rein - gk_soll)},
        "fusion_report": {"kapital": fus, "einzahlungen": r2(eur(fus_ein)), "auszahlungen": r2(eur(fus_aus)),
                          "hedge_ergebnis": r2(hedge_ergebnis)},
        "abweichung": r2(abw), "toleranz": r2(toleranz), "auffaellig": abs(abw) > toleranz, "kauf": r2(kauf),
        "abfluesse": abfl[:200], "abfluesse_summe": r2(sum(z["betrag_eur"] for z in abfl)), "abfluesse_n": len(abfl),
        "zufluesse": zufl[:200], "zufluesse_summe": r2(sum(z["betrag_eur"] for z in zufl)), "zufluesse_n": len(zufl),
        "gefiltert": gef,
    }


def _daten_lesen(gid):
    """Alle Zeilen für bilanz_rechnen. Fehler fliegen durch (Aufrufer antwortet 502)."""
    kurs = tageskurs()
    fx = kurs["fx"]
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
    # Fusion live: Hedge-Logins = external_id der Live-Konten der Gruppe (Emin-Gruppe: alle fünf IDs auf 430095 → einmal zählen)
    logins = {str(a.get("external_id") or "").strip() for a in
              (A["_sb_all"]("accounts", {"select": "id,external_id", "account_type": "eq.live", "user_id": _in(mit)}) if mit else [])}
    logins.discard("")
    fus_live = None
    if logins:
        zeilen = _sb("GET", "mt5_live", {"select": "hedge_login,updated_at,status", "hedge_login": _in(logins),
                                         "order": "updated_at.desc", "limit": "50"}) or []
        fus_live = fusion_live_waehlen(zeilen, logins)
    offene = (_sb("GET", "pending_payouts", {"select": "amount,currency", "status": "eq.pending", "user_id": _in(mit)}) or []) if mit else []
    fus = _sb("GET", "kapital_fusion", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "created_at.desc", "limit": "1"}) or []
    einl = A["_sb_all"]("kapital_einlagen", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "datum.asc,id.asc"})
    gk = A["_sb_all"]("kapital_gk_buchungen", {"select": "*", "gruppe_id": f"eq.{gid}", "order": "datum.asc,id.asc"})
    tx = A["_sb_all"]("wallet_tx", {"select": "tx_key,wallet_id,chain,person_name,hash,ts,dir,amount,sym,other,kategorie,kommentar",
                                    "wallet_id": _in(wids), "order": "ts.desc,id.asc"}) if wids else []
    adressen = {str(w["address"]).lower() for w in wallets}
    others = sorted({str(t.get("other") or "").lower() for t in tx if t.get("other")})
    labels = {}
    for i in range(0, len(others), 150):               # URL-Länge: in Häppchen; wallet_labels speichert die Adresse klein
        for l in _sb("GET", "wallet_labels", {"select": "address,kind", "address": _in(others[i:i + 150])}) or []:
            labels[str(l["address"]).lower()] = l.get("kind") or ""
    return {"kurs": kurs, "ketten": ketten, "snaps": snaps, "fusion_live": fus_live, "fusion_hand": fus[0] if fus else None,
            "einlagen": einl, "gk": gk, "tx": tx, "labels": labels, "adressen": adressen, "wallets_n": len(wallets), "offene": offene}


def _tageswert_schreiben(gid, b):
    A["sb_upsert"]("kapital_tageswerte", {
        "gruppe_id": gid, "tag": _heute().isoformat(), "ist_eur": b["ist"]["summe"], "soll_eur": b["soll"]["summe"],
        "abweichung_eur": b["abweichung"], "updated_at": datetime.now(timezone.utc).isoformat(),
        "teile": {"ist": b["ist"], "soll": b["soll"], "fusion_report": b["fusion_report"], "toleranz": b["toleranz"],
                  "abfluesse_summe": b["abfluesse_summe"], "abfluesse_n": b["abfluesse_n"], "kurs": b["kurs"]}})


def kapital_fuer(gid, schreiben=True):
    d = _daten_lesen(gid)
    b = bilanz_rechnen(d["ketten"], d["snaps"], d["fusion_live"], d["fusion_hand"], d["einlagen"], d["tx"], d["labels"], d["adressen"],
                       d["kurs"]["fx"], d["offene"], d["gk"])
    b["kurs"] = d["kurs"]
    b["ist"]["wallets_gesamt_n"] = d["wallets_n"]
    if schreiben:
        try:
            _tageswert_schreiben(gid, b)
        except Exception as e:
            print(f"[kapital] ⚠️ Tageswert: {type(e).__name__}: {e}", flush=True)
    fx = d["kurs"]["fx"]
    b["einlagen"] = [{"id": e["id"], "betrag": _num(e["betrag"]), "waehrung": e.get("waehrung") or "EUR",
                      "betrag_eur": round(_num(e["betrag"]) * (fx if (e.get("waehrung") or "EUR") == "USD" else 1), 2),
                      "datum": e.get("datum"), "ziel_wallet": e.get("ziel_wallet") or "", "notiz": e.get("notiz") or "",
                      "quelle_tx": e.get("quelle_tx") or ""} for e in d["einlagen"]]
    b["gk_buchungen"] = [{"id": g["id"], "datum": g.get("datum"), "betrag": _num(g["betrag"]), "waehrung": g.get("waehrung") or "EUR",
                          "kategorie": g.get("kategorie") or "", "text": g.get("text") or ""} for g in reversed(d["gk"])]
    b["gk_kategorien"] = GK_KATEGORIEN
    b["verlauf"] = [{"tag": r["tag"], "ist": _num(r["ist_eur"]), "soll": _num(r["soll_eur"]), "abw": _num(r["abweichung_eur"])}
                    for r in A["_sb_all"]("kapital_tageswerte", {"select": "tag,ist_eur,soll_eur,abweichung_eur",
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
    return str(getattr(g, "kapital_uid", "") or request.environ.get("prophos.admin_uid") or "")


def _gate():
    """Gate wie /admin/overview (_wd_login: eingeloggt) plus: NICHT eingeschränkt. _wd_login setzt g.admin_sicht nur für eingeschränkte
    Logins (Verwalter einer Gruppe, Mitglied, „nur eigene“) — die bekommen 403, die Zahl ist Finns Kontrolle über die Gruppe. Bewusst nicht
    mehr _lq_gate (ADMIN_EMAILS): Vorfall 29.10.2026 04:25, Finn als „Finn + Pascal“ (Voll-Admin im Admin, aber nicht in ADMIN_EMAILS) sah
    nur „Nur für Voll-Admins.“ → None oder (Antwort, Status)."""
    uid, err = A["_wd_login"]()
    if err:
        return err
    if getattr(g, "admin_sicht", None) is not None:
        return jsonify({"ok": False, "error": "Nur für Logins ohne Einschränkung im Admin"}), 403
    g.kapital_uid = uid
    return None


def _datum(v):
    v = str(v or "").strip() or _heute().isoformat()
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else ""


def _loeschen(tabelle, body):
    eid = _uuid(body.get("id"))
    if not eid:
        return jsonify({"ok": False, "error": "id nötig"}), 400
    weg = _sb("DELETE", tabelle, {"id": f"eq.{eid}"}, prefer="return=representation") or []
    return jsonify({"ok": True}) if weg else (jsonify({"ok": False, "error": "nicht gefunden"}), 404)


def registrieren(app, ns):
    """Routen an die Flask-App hängen; auf Railway den Stunden-Takt starten (auf den PCs ist PROPHOS_FRONTEND gesetzt — dort nie)."""
    A.update(ns)

    @app.route("/admin/kapital", methods=["GET", "OPTIONS"])
    def admin_kapital():
        if request.method == "OPTIONS":
            return "", 200
        err = _gate()
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
        err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "DELETE":
                return _loeschen("kapital_einlagen", body)
            gid, betrag, datum = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("datum"))
            w = str(body.get("waehrung") or "EUR").upper()
            if not gid or not (betrag > 0) or not datum or w not in ("EUR", "USD"):
                return jsonify({"ok": False, "error": "gruppe, betrag > 0, waehrung EUR/USD und datum (JJJJ-MM-TT) nötig"}), 400
            neu = A["sb_insert"]("kapital_einlagen", {
                "gruppe_id": gid, "betrag": round(betrag, 2), "waehrung": w, "datum": datum,
                "ziel_wallet": str(body.get("ziel_wallet") or "").strip()[:120] or None,
                "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                "quelle_tx": str(body.get("quelle_tx") or "").strip()[:200] or None, "angelegt_von": _admin_uid() or None})
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
        err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        gid, betrag, stand = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("stand_am"))
        w = str(body.get("waehrung") or "EUR").upper()
        if not gid or betrag < 0 or w not in ("EUR", "USD") or not stand:
            return jsonify({"ok": False, "error": "gruppe, betrag ≥ 0, waehrung EUR/USD und stand_am nötig"}), 400
        try:
            neu = A["sb_insert"]("kapital_fusion", {"gruppe_id": gid, "betrag": round(betrag, 2), "waehrung": w, "stand_am": stand,
                                                    "notiz": str(body.get("notiz") or "").strip()[:300] or None,
                                                    "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "fusion": neu})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    @app.route("/admin/kapital/gk", methods=["POST", "DELETE", "OPTIONS"])
    def admin_kapital_gk():
        """Geschäftskonto-Buchung (Finn 29.10.2026: „wie in so einem Google-Sheet … Kunden bezahlen oder PCs kaufen")."""
        if request.method == "OPTIONS":
            return "", 200
        err = _gate()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            if request.method == "DELETE":
                return _loeschen("kapital_gk_buchungen", body)
            gid, betrag, datum = _uuid(body.get("gruppe")), _num(body.get("betrag")), _datum(body.get("datum"))
            w = str(body.get("waehrung") or "EUR").upper()
            kat = str(body.get("kategorie") or "Sonstiges").strip()[:40] or "Sonstiges"
            if not gid or betrag == 0 or not datum or w not in ("EUR", "USD"):
                return jsonify({"ok": False, "error": "gruppe, betrag ≠ 0 (+ Eingang / − Ausgang), waehrung und datum nötig"}), 400
            neu = A["sb_insert"]("kapital_gk_buchungen", {
                "gruppe_id": gid, "datum": datum, "betrag": round(betrag, 2), "waehrung": w, "kategorie": kat,
                "text": str(body.get("text") or "").strip()[:300] or None, "angelegt_von": _admin_uid() or None})
            return jsonify({"ok": True, "buchung": neu})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 502

    if (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "").strip() \
            and not os.environ.get("PROPHOS_FRONTEND"):
        threading.Thread(target=_takt_schleife, name="kapital-takt", daemon=True).start()

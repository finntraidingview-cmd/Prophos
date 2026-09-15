#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tsx_stream_test.py — Test-Harnisch für den ProjectX/TopstepX User-Hub (SignalR).

Zweck (15.09.2026): Der Echtzeit-Mirror in app.py bekommt vom User-Hub nie ein Event —
der Server schließt ~2 s nach dem Verbinden, ohne Fehlertext, ohne Subscribe-Completion.
Dieses Script verbindet sich EINMAL (kein Auto-Reconnect), protokolliert jeden Schritt mit
Millisekunden-Zeitstempel und druckt am Ende eine Zusammenfassung.

Aufruf:
    python3 tsx_stream_test.py <JWT> <accountId> [Optionen]

Optionen:
    --negotiate       Standard-SignalR-Negotiate (POST /negotiate) statt Direktverbindung
    --messagepack     MessagePack- statt JSON-Protokoll (nur signalrcore-Modus)
    --no-subscribe    nur verbinden, nichts abonnieren (isoliert: schließt der Server auch
                      OHNE Abo nach 2 s?)
    --only Trades     nur einzelne Kanäle abonnieren, kommagetrennt aus
                      Accounts,Orders,Positions,Trades
    --hs-version N    Handshake-Version erzwingen. signalrcore 1.0.2 schickt ohne diese
                      Option {"protocol":"json","version":0} (Befund 15.09.2026) — der
                      offizielle JS-Client schickt version 1. Mit --hs-version 1 wird
                      exakt das JS-Verhalten nachgestellt.
    --duration S      Laufzeit in Sekunden (Standard 60), endet früher bei Close
    --raw             Roh-Modus: eigener Minimal-WebSocket-Client (nur stdlib: socket+ssl),
                      hexdumpt JEDEN Frame in beide Richtungen — Handshake und CloseMessage
                      byte-genau, inkl. WebSocket-Close-Code und -Reason, die signalrcore
                      verschluckt. Im Roh-Modus wird immer version 1 geschickt (JS-Parität),
                      es sei denn --hs-version sagt etwas anderes.
    --ua "…"          (nur --raw) User-Agent-Header mitschicken (signalrcore schickt keinen)
    --origin "…"      (nur --raw) Origin-Header mitschicken (Browser schicken einen)
    --auth-header     (nur --raw) zusätzlich Authorization: Bearer <JWT> im Upgrade-Request
    --verbose         auch die DEBUG-Zeilen der Library zeigen (signalrcore-Modus)

Keine Credentials im Script, kein Login — das JWT kommt IMMER von der Kommandozeile.
"""
import argparse
import base64
import copy
import json
import logging
import os
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

RTC_BASE = os.environ.get("TSX_RTC_BASE", "https://rtc.topstepx.com")   # Override nur für Tests gegen einen Mock
HUB_PATH = "/hubs/user"
EVENT_NAMES = ["GatewayUserTrade", "GatewayUserPosition", "GatewayUserOrder",
               "GatewayUserAccount", "GatewayLogout"]
ALL_SUBS = ["Accounts", "Orders", "Positions", "Trades"]
RS = "\x1e"

T0 = time.time()


# ── Logging ──────────────────────────────────────────────────────────────────
def ts():
    now = time.time()
    return "[%s.%03d +%7.3fs]" % (time.strftime("%H:%M:%S", time.localtime(now)),
                                  int((now % 1) * 1000), now - T0)


def log(tag, msg):
    print("%s %-10s %s" % (ts(), tag, msg), flush=True)


def short(x, n=240):
    if isinstance(x, (bytes, bytearray)):
        s = x.hex()
    elif isinstance(x, str):
        s = x
    else:
        try:
            s = json.dumps(x, default=str, ensure_ascii=False)
        except Exception:
            s = str(x)
    s = s.replace(RS, "⏎")
    return s if len(s) <= n else s[:n] + "… (%d Zeichen)" % len(s)


def hexdump(data, max_bytes=256):
    """Klassischer Hexdump: Offset · 16 Bytes hex · ASCII. Für den Roh-Modus."""
    out = []
    data = bytes(data)
    for off in range(0, min(len(data), max_bytes), 16):
        chunk = data[off:off + 16]
        hx = " ".join("%02x" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("      %04x  %-47s  %s" % (off, hx, asc))
    if len(data) > max_bytes:
        out.append("      … %d weitere Bytes" % (len(data) - max_bytes))
    return "\n".join(out)


# ── Gemeinsamer Zustand für die Zusammenfassung ──────────────────────────────
class State(object):
    def __init__(self):
        self.socket_open = None      # Zeitpunkt 101
        self.handshake_sent = None
        self.handshake_ok = None
        self.handshake_error = None
        self.sent = {}               # invocationId -> (name, t)
        self.confirmed = {}          # name -> (t, error)
        self.events = {}             # eventname -> count
        self.first_event = None
        self.close_msg = None        # (t, fields-dict)
        self.ws_close = None         # (t, code, reason)
        self.socket_close = None
        self.errors = []
        self.done = threading.Event()

    def mark_event(self, name):
        self.events[name] = self.events.get(name, 0) + 1
        if self.first_event is None:
            self.first_event = time.time()


def summary(S, mode):
    print("\n" + "=" * 78)
    print("ZUSAMMENFASSUNG (%s)" % mode)
    print("=" * 78)

    def rel(t):
        return "nach %.3f s" % (t - T0) if t else "—"

    print("Socket verbunden (101):     %s" % ("ja, " + rel(S.socket_open) if S.socket_open else "NEIN"))
    if S.handshake_ok:
        print("Handshake-Antwort:          OK, %s" % rel(S.handshake_ok))
    elif S.handshake_error:
        print("Handshake-Antwort:          FEHLER: %s" % S.handshake_error)
    else:
        print("Handshake-Antwort:          KEINE (Server hat nie geantwortet)")
    if S.sent:
        for iid, (name, t) in sorted(S.sent.items(), key=lambda kv: kv[1][1]):
            c = S.confirmed.get(name)
            if c:
                st = "bestätigt %s%s" % (rel(c[0]), (" — FEHLER: %s" % c[1]) if c[1] else "")
            else:
                st = "OHNE Completion"
            print("  Abo %-18s id=%s → %s" % (name, iid, st))
    else:
        print("Abonnements:                keine gesendet")
    if S.events:
        print("Events:                     " + ", ".join("%s×%d" % kv for kv in S.events.items())
              + " (erstes %s)" % rel(S.first_event))
    else:
        print("Events:                     KEINE")
    if S.close_msg:
        t, fields = S.close_msg
        print("CloseMessage vom Server:    %s — Felder: %s" % (rel(t), json.dumps(fields, default=str)))
    else:
        print("CloseMessage vom Server:    keine")
    if S.ws_close:
        t, code, reason = S.ws_close
        print("WebSocket-Close-Frame:      %s — Code %s, Reason %r" % (rel(t), code, reason))
    print("Socket geschlossen:         %s" % ("ja, " + rel(S.socket_close) if S.socket_close else "nein (Laufzeit abgelaufen)"))
    ref = S.handshake_ok or S.socket_open
    end = S.socket_close or (S.close_msg[0] if S.close_msg else None)
    if ref and end:
        print("Sekunden Handshake→Close:   %.3f s" % (end - ref))
    if S.errors:
        print("Fehler:")
        for e in S.errors:
            print("  - %s" % e)
    print("=" * 78)


# ── Modus A: signalrcore 1.0.2 (die Library, die app.py benutzt) ─────────────
def run_signalrcore(a, S):
    from signalrcore.hub_connection_builder import HubConnectionBuilder
    from signalrcore.transport.websockets.websocket_transport import WebsocketTransport
    from signalrcore.messages.message_type import MessageType
    from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
    from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol

    # Library-Logs mit Zeitstempel durchreichen (DEBUG nur mit --verbose, Negotiate immer)
    class _H(logging.Handler):
        def emit(self, record):
            try:
                m = record.getMessage()
                if record.levelno >= logging.WARNING or a.verbose or m.startswith("Negotiate"):
                    log("LIB-" + record.levelname[:4], short(m, 300))
                if record.levelno >= logging.ERROR:
                    S.errors.append(short(m, 200))
            except Exception:
                pass

    # ── Transport-Patches: sichtbar machen, was die Library sonst nur auf DEBUG loggt ──
    _orig_open = WebsocketTransport.on_socket_open

    def p_open(self):
        S.socket_open = time.time()
        log("SOCKET", "offen — HTTP 101 erhalten, Empfangs-Thread läuft")
        return _orig_open(self)

    _orig_send = WebsocketTransport.send

    def p_send(self, message):
        name = type(message).__name__
        iid = getattr(message, "invocation_id", None) or getattr(message, "invocationId", None)
        try:
            # Kopie encoden: JsonHubProtocol.MyEncoder.default() mutiert das Objekt (löscht
            # invocation_id, setzt invocationId) — ein zweites Encode/__repr__ crasht sonst.
            enc = self.protocol.encode(copy.copy(message))
        except Exception as e:
            enc = "<encode-Fehler %s>" % e
        if name == "HandshakeRequestMessage":
            S.handshake_sent = time.time()
            log("SEND", "Handshake: %s" % short(enc))
        elif name == "PingMessage":
            log("SEND", "Client-Ping: %s" % short(enc))
        else:
            log("SEND", "%s id=%s: %s" % (name, iid, short(enc)))
        return _orig_send(self, message)

    _orig_eval = WebsocketTransport.evaluate_handshake

    def p_eval(self, raw):
        log("RECV", "Handshake-Antwort roh: %s" % short(raw))
        try:
            msg, _rest = self.protocol.decode_handshake(raw)
            if msg.error:
                S.handshake_error = msg.error
                log("HANDSHAKE", "FEHLER vom Server: %s" % msg.error)
            else:
                S.handshake_ok = time.time()
                log("HANDSHAKE", "OK — Server hat Protokoll akzeptiert")
        except Exception as e:
            S.handshake_error = "decode: %s" % e
            log("HANDSHAKE", "Antwort nicht dekodierbar: %s" % e)
        return _orig_eval(self, raw)

    _orig_on_message = WebsocketTransport.on_message

    def p_on_message(self, app, raw):
        if self.handshake_received:
            log("RECV", "Frame: %s" % short(raw))
        return _orig_on_message(self, app, raw)

    _orig_sock_close = WebsocketTransport.on_socket_close

    def p_sock_close(self):
        if S.socket_close is None:
            S.socket_close = time.time()
        log("SOCKET", "geschlossen (signalrcore liest Close-Code/Reason NICHT — dafür --raw)")
        r = _orig_sock_close(self)
        S.done.set()
        return r

    _orig_sock_err = WebsocketTransport.on_socket_error

    def p_sock_err(self, err):
        log("SOCKET", "Fehler: %s" % short(str(err), 200))
        S.errors.append("socket: %s" % short(str(err), 200))
        return _orig_sock_err(self, err)

    WebsocketTransport.on_socket_open = p_open
    WebsocketTransport.send = p_send
    WebsocketTransport.evaluate_handshake = p_eval
    WebsocketTransport.on_message = p_on_message
    WebsocketTransport.on_socket_close = p_sock_close
    WebsocketTransport.on_socket_error = p_sock_err

    url = "%s%s?access_token=%s" % (RTC_BASE, HUB_PATH, a.jwt)
    b = HubConnectionBuilder() \
        .with_url(url, options={"skip_negotiation": not a.negotiate}) \
        .configure_logging(logging.DEBUG, handler=_H())
    if a.hs_version is not None:
        proto = MessagePackHubProtocol(version=a.hs_version) if a.messagepack \
            else JsonHubProtocol(version=a.hs_version)
        b = b.with_hub_protocol(proto)
        log("SETUP", "Handshake-Version erzwungen: %d (%s)" % (a.hs_version, "messagepack" if a.messagepack else "json"))
    elif a.messagepack:
        b = b.with_hub_protocol(MessagePackHubProtocol())
        log("SETUP", "MessagePack mit Library-Standardversion")
    else:
        log("SETUP", "Library-Standard: signalrcore leitet die Handshake-Version aus negotiateVersion ab "
                     "(Direktmodus → 0!). Vergleich mit JS: --hs-version 1")
    hub = b.build()   # KEIN with_automatic_reconnect — wir wollen den ersten Close sehen

    # Hub-Nachrichten auf Nachrichten-Ebene loggen (Completion/Event/Ping/Close)
    _orig_hub_on_message = hub.on_message

    def hub_on_message(messages):
        for m in messages:
            t = m.type
            if t == MessageType.completion:
                name = S.sent.get(m.invocation_id, ("?", 0))[0]
                err = m.error
                S.confirmed[name] = (time.time(), err)
                log("COMPLETION", "invocationId=%s (%s) error=%r result=%s" % (m.invocation_id, name, err, short(m.result)))
            elif t == MessageType.invocation:
                S.mark_event(m.target)
                log("EVENT", "%s args=%s" % (m.target, short(m.arguments)))
            elif t == MessageType.ping:
                log("PING", "Server-Ping empfangen")
            elif t == MessageType.close:
                fields = dict((k, v) for k, v in vars(m).items() if k != "type")
                S.close_msg = (time.time(), fields)
                log("CLOSE", "CloseMessage vom Server — ALLE Felder: %s" % json.dumps(fields, default=str))
            else:
                log("MSG", "%s %s" % (t, short(vars(m))))
        return _orig_hub_on_message(messages)
    hub.on_message = hub_on_message   # BaseHubConnection.start() übergibt self.on_message → Instanz-Attribut greift

    subs = subs_for(a)

    def mk_conf(name):
        def cb(completion):
            log("CONFIRM", "%s vom Server bestätigt (on_invocation)" % name)
        return cb

    def on_open():
        log("HUB", "on_open — signalrcore bindet on_open an die Handshake-ANTWORT (nicht an den Socket-Open)")
        if a.no_subscribe:
            log("HUB", "--no-subscribe: nichts abonniert")
            return
        for name, args in subs:
            try:
                r = hub.send(name, args, on_invocation=mk_conf(name))
                S.sent[r.invocation_id] = (name, time.time())
                log("INVOKE", "%s%s invocationId=%s" % (name, json.dumps(args), r.invocation_id))
            except Exception as e:
                S.errors.append("send %s: %s" % (name, e))
                log("INVOKE", "%s FEHLGESCHLAGEN: %s" % (name, e))

    def on_close():
        log("HUB", "on_close")
        if S.socket_close is None:
            S.socket_close = time.time()
        S.done.set()

    def on_error(e):
        err = getattr(e, "error", None)
        iid = getattr(e, "invocation_id", None)
        log("HUB", "on_error: invocationId=%s error=%s" % (iid, short(err or e, 300)))
        S.errors.append("on_error %s: %s" % (iid, short(err or e, 200)))
        if iid in S.sent:
            S.confirmed[S.sent[iid][0]] = (time.time(), str(err or e))

    hub.on_open(on_open)
    hub.on_close(on_close)
    hub.on_error(on_error)
    for ev in EVENT_NAMES:
        hub.on(ev, (lambda name: (lambda args: None))(ev))   # Zählung passiert oben im Wrapper

    log("SETUP", "Modus: %s · Ziel: %s · Abos: %s" % (
        "Negotiate" if a.negotiate else "Direkt (skip_negotiation)", url.split("?")[0],
        "keine" if a.no_subscribe else ", ".join(n for n, _ in subs)))
    try:
        hub.start()
    except Exception as e:
        log("SETUP", "start() fehlgeschlagen: %s: %s" % (type(e).__name__, e))
        S.errors.append("start: %s" % e)
        S.done.set()

    S.done.wait(a.duration)
    if not S.done.is_set():
        log("ENDE", "Laufzeit %ds abgelaufen — Verbindung steht noch, wird jetzt getrennt" % a.duration)
    # Endgültig trennen wie app.py:_hub_kill — hub.stop() allein kehrt zurück, wenn der
    # Transport gerade 'disconnected' ist, und lässt den Socket sonst offen.
    try:
        t = hub.transport
        if t is not None:
            t.manually_closing = True
            try: t.connection_checker.stop()
            except Exception: pass
            c = getattr(t, "_client", None)
            if c is not None:
                c.close()
    except Exception:
        pass
    summary(S, "signalrcore 1.0.2")


def subs_for(a):
    acc = int(a.account_id)
    wanted = ALL_SUBS
    if a.only:
        wanted = [w.strip().capitalize() for w in a.only.split(",") if w.strip()]
        bad = [w for w in wanted if w not in ALL_SUBS]
        if bad:
            sys.exit("--only: unbekannte Kanäle %s (erlaubt: %s)" % (bad, ", ".join(ALL_SUBS)))
    return [("Subscribe" + w, [] if w == "Accounts" else [acc]) for w in wanted]


# ── Modus B: Roh-WebSocket (stdlib), byte-genau ──────────────────────────────
def ws_frame(payload, opcode=0x1):
    """Client-Frame bauen (maskiert, unfragmentiert) — RFC 6455 §5.2."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n <= 125:
        head += bytes([0x80 | n])
    elif n <= 65535:
        head += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", n)
    mask = os.urandom(4)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


OPCODES = {0x0: "CONT", 0x1: "TEXT", 0x2: "BINARY", 0x8: "CLOSE", 0x9: "PING", 0xA: "PONG"}


def run_raw(a, S):
    token = a.jwt
    url = "%s%s?access_token=%s" % (RTC_BASE, HUB_PATH, token)
    hs_version = 1 if a.hs_version is None else a.hs_version

    if a.negotiate:
        # Wie der JS-Client OHNE skipNegotiation: POST …/negotiate?negotiateVersion=1
        neg_url = "%s%s/negotiate?negotiateVersion=1&access_token=%s" % (RTC_BASE, HUB_PATH, token)
        req = urllib.request.Request(neg_url, method="POST", data=b"",
                                     headers={"Content-Length": "0", "X-Requested-With": "XMLHttpRequest",
                                              "Authorization": "Bearer " + token})
        log("NEGOTIATE", "POST %s" % neg_url.split("?")[0] + "?negotiateVersion=1&access_token=…")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode("utf-8", "replace")
                log("NEGOTIATE", "HTTP %s: %s" % (r.status, short(body, 400)))
                data = json.loads(body)
        except urllib.error.HTTPError as e:
            log("NEGOTIATE", "HTTP %s: %s" % (e.code, short(e.read().decode("utf-8", "replace"), 300)))
            S.errors.append("negotiate HTTP %s" % e.code)
            summary(S, "raw")
            return
        cid = data.get("connectionToken") or data.get("connectionId")
        if data.get("url"):   # Azure-SignalR-Redirect
            url = data["url"] + ("&" if "?" in data["url"] else "?") + "access_token=" + data.get("accessToken", token)
            log("NEGOTIATE", "Azure-Redirect auf %s" % url.split("?")[0])
        else:
            url += "&id=" + urllib.parse.quote(cid)
        log("NEGOTIATE", "negotiateVersion=%s connectionId=%s connectionToken=%s transports=%s" % (
            data.get("negotiateVersion"), data.get("connectionId"),
            (data.get("connectionToken") or "")[:12] + "…" if data.get("connectionToken") else None,
            [t.get("transport") for t in data.get("availableTransports", [])]))

    p = urllib.parse.urlparse(url)
    secure = p.scheme in ("https", "wss")
    host, port = p.hostname, p.port or (443 if secure else 80)
    path = p.path + ("?" + p.query if p.query else "")
    key = base64.b64encode(os.urandom(16)).decode()
    lines = ["GET %s HTTP/1.1" % path, "Host: %s" % host, "Upgrade: websocket", "Connection: Upgrade",
             "Sec-WebSocket-Key: %s" % key, "Sec-WebSocket-Version: 13"]
    if a.ua:
        lines.append("User-Agent: %s" % a.ua)
    if a.origin:
        lines.append("Origin: %s" % a.origin)
    if a.auth_header:
        lines.append("Authorization: Bearer %s" % token)
    req = ("\r\n".join(lines) + "\r\n\r\n").encode()

    log("SETUP", "Roh-Modus · %s · Handshake-Version %d · Header: %s" % (
        "Negotiate" if a.negotiate else "Direkt", hs_version,
        ", ".join(l.split(":")[0] for l in lines[1:])))
    raw = socket.create_connection((host, port), timeout=15)
    if secure:
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        log("TLS", "verbunden mit %s:%d · %s · ALPN=%s" % (host, port, sock.version(), sock.selected_alpn_protocol()))
    else:
        sock = raw
        log("TCP", "verbunden mit %s:%d (ohne TLS — nur für Mock-Tests)" % (host, port))
    log("SEND", "HTTP-Upgrade-Request (%d Bytes):\n%s" % (len(req), hexdump(req.replace(token.encode(), b"<JWT>"), 96)))
    sock.sendall(req)

    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            log("SOCKET", "Server hat während des HTTP-Upgrades geschlossen. Bisher: %r" % buf[:300])
            S.errors.append("Upgrade: Verbindung zu")
            summary(S, "raw")
            return
        buf += chunk
    head, buf = buf.split(b"\r\n\r\n", 1)
    head_txt = head.decode("utf-8", "replace")
    status = head_txt.split("\r\n")[0]
    log("RECV", "HTTP-Antwort: %s" % status)
    for hl in head_txt.split("\r\n")[1:]:
        log("RECV", "   %s" % hl)
    if " 101 " not in status:
        log("SOCKET", "Kein 101 — Body: %r" % buf[:400])
        S.errors.append("Upgrade: %s" % status)
        summary(S, "raw")
        return
    S.socket_open = time.time()
    if buf:
        log("RECV", "ACHTUNG: %d Bytes kamen bereits mit dem 101 — signalrcore würde sie VERWERFEN:\n%s" % (len(buf), hexdump(buf)))

    lock = threading.Lock()
    running = [True]

    def send_text(s, tag):
        fr = ws_frame(s, 0x1)
        with lock:
            sock.sendall(fr)
        log("SEND", "%s TEXT-Frame (%d Bytes Payload): %s\n%s" % (tag, len(s.encode()), short(s), hexdump(fr, 80)))

    def recv_exact(n):
        nonlocal buf
        while len(buf) < n:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                if not running[0]:
                    raise OSError("stop")
                continue
            if not chunk:
                raise OSError("EOF")
            buf += chunk
        out, buf = buf[:n], buf[n:]
        return out

    def classify(text):
        for rec in text.split(RS):
            if not rec:
                continue
            try:
                m = json.loads(rec)
            except Exception:
                log("RECV", "   nicht-JSON-Record: %r" % rec[:200])
                continue
            t = m.get("type")
            if t is None:      # Handshake-Antwort {} oder {"error":…}
                if m.get("error"):
                    S.handshake_error = m["error"]
                    log("HANDSHAKE", "FEHLER vom Server: %s" % m["error"])
                else:
                    S.handshake_ok = time.time()
                    log("HANDSHAKE", "OK — Antwort %s" % json.dumps(m))
                hs_done.set()
            elif t == 3:
                name = S.sent.get(m.get("invocationId"), ("?", 0))[0]
                S.confirmed[name] = (time.time(), m.get("error"))
                log("COMPLETION", "invocationId=%s (%s) error=%r result=%s" % (m.get("invocationId"), name, m.get("error"), short(m.get("result"))))
            elif t == 1:
                S.mark_event(m.get("target"))
                log("EVENT", "%s args=%s" % (m.get("target"), short(m.get("arguments"))))
            elif t == 6:
                log("PING", "Server-Ping {\"type\":6}")
            elif t == 7:
                fields = dict((k, v) for k, v in m.items() if k != "type")
                S.close_msg = (time.time(), fields)
                log("CLOSE", "CloseMessage vom Server — ALLE Felder: %s" % json.dumps(fields))
            else:
                log("MSG", "type=%s %s" % (t, short(m)))

    hs_done = threading.Event()

    def reader():
        sock.settimeout(1.0)
        frag = b""
        try:
            while running[0]:
                h = recv_exact(2)
                fin, opcode, ln = bool(h[0] & 0x80), h[0] & 0x0F, h[1] & 0x7F
                masked = bool(h[1] & 0x80)
                ext = b""
                if ln == 126:
                    ext = recv_exact(2); ln = struct.unpack(">H", ext)[0]
                elif ln == 127:
                    ext = recv_exact(8); ln = struct.unpack(">Q", ext)[0]
                payload = recv_exact(ln)
                log("FRAME", "← %s fin=%d masked=%d len=%d\n%s" % (OPCODES.get(opcode, "0x%x" % opcode), fin, masked, ln, hexdump(h + ext + payload)))
                if opcode == 0x8:
                    code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
                    reason = payload[2:].decode("utf-8", "replace")
                    S.ws_close = (time.time(), code, reason)
                    log("CLOSE", "WebSocket-Close-Frame: Code=%s Reason=%r (signalrcore zeigt das nie)" % (code, reason))
                    try:
                        with lock:
                            sock.sendall(ws_frame(struct.pack(">H", 1000), 0x8))
                        log("SEND", "Close-Frame 1000 zurückgeschickt")
                    except Exception:
                        pass
                    break
                if opcode == 0x9:
                    with lock:
                        sock.sendall(ws_frame(payload, 0xA))
                    log("SEND", "PONG als Antwort auf Server-PING (signalrcore antwortet NICHT auf WS-Pings)")
                    continue
                if opcode == 0xA:
                    log("FRAME", "   (unsolicited PONG — Keep-Alive des Servers)")
                    continue
                frag += payload
                if not fin:
                    continue
                data, frag = frag, b""
                if opcode in (0x1, 0x0):
                    classify(data.decode("utf-8", "replace"))
                else:
                    log("RECV", "Binär-Payload (%d Bytes) — MessagePack? hier nicht dekodiert" % len(data))
        except OSError as e:
            if running[0]:
                log("SOCKET", "Lesen beendet: %s" % e)
        finally:
            if S.socket_close is None:
                S.socket_close = time.time()
            log("SOCKET", "geschlossen")
            running[0] = False
            S.done.set()

    th = threading.Thread(target=reader, name="raw-reader", daemon=True)
    th.start()

    hs = json.dumps({"protocol": "messagepack" if a.messagepack else "json", "version": hs_version}, separators=(",", ":")) + RS
    S.handshake_sent = time.time()
    send_text(hs, "Handshake")
    if not hs_done.wait(15):
        log("HANDSHAKE", "KEINE Antwort binnen 15 s")
    elif S.handshake_ok and not a.no_subscribe:
        # JS-Stil: invocationId als laufende Zahl, KEIN headers-Feld
        for i, (name, args) in enumerate(subs_for(a)):
            iid = str(i)
            msg = json.dumps({"type": 1, "invocationId": iid, "target": name, "arguments": args}, separators=(",", ":")) + RS
            S.sent[iid] = (name, time.time())
            send_text(msg, "Invocation %s" % name)
    elif a.no_subscribe:
        log("HUB", "--no-subscribe: nichts abonniert")

    deadline = time.time() + a.duration
    last_ping = time.time()
    while running[0] and time.time() < deadline:
        S.done.wait(0.25)
        if S.done.is_set():
            break
        if time.time() - last_ping >= 10:   # Client-Keep-Alive wie signalrcore (10 s)
            try:
                send_text('{"type":6}' + RS, "Client-Ping")
            except Exception as e:
                log("SEND", "Ping fehlgeschlagen: %s" % e)
                break
            last_ping = time.time()
    if running[0]:
        log("ENDE", "Laufzeit abgelaufen — Verbindung steht noch, sende Close 1000")
        running[0] = False
        try:
            with lock:
                sock.sendall(ws_frame(struct.pack(">H", 1000), 0x8))
        except Exception:
            pass
    try:
        sock.close()
    except Exception:
        pass
    th.join(3)
    summary(S, "raw (stdlib) · Handshake-Version %d" % hs_version)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="TopstepX/ProjectX User-Hub Stream-Test (ein Verbindungsversuch, kein Reconnect)")
    ap.add_argument("jwt", help="TSX-JWT (Bearer-Token) — nur von der Kommandozeile")
    ap.add_argument("account_id", help="TSX accountId (int)")
    ap.add_argument("--negotiate", action="store_true")
    ap.add_argument("--messagepack", action="store_true")
    ap.add_argument("--no-subscribe", action="store_true")
    ap.add_argument("--only", default=None, help="z.B. Trades oder Positions,Trades")
    ap.add_argument("--hs-version", type=int, default=None)
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--ua", default=None)
    ap.add_argument("--origin", default=None)
    ap.add_argument("--auth-header", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    if a.jwt.count(".") != 2:
        print("Hinweis: das erste Argument sieht nicht wie ein JWT aus (erwartet xxx.yyy.zzz)", file=sys.stderr)
    int(a.account_id)
    S = State()
    log("START", "tsx_stream_test · Python %s · Ziel %s%s · accountId %s · %ds" % (
        sys.version.split()[0], RTC_BASE, HUB_PATH, a.account_id, a.duration))
    if a.raw:
        run_raw(a, S)
    else:
        try:
            import signalrcore  # noqa: F401
        except ImportError:
            sys.exit("signalrcore fehlt — pip3 install signalrcore, oder --raw benutzen (nur stdlib)")
        run_signalrcore(a, S)


if __name__ == "__main__":
    main()

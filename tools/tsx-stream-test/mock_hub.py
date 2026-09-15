"""Mini-SignalR-Server (stdlib) zum Offline-Test des Harnischs: 101, Handshake-Ack, eine
Completion pro Invocation, ein Event, dann CloseMessage + WS-Close-Frame nach ~2 s."""
import socket, threading, base64, hashlib, struct, json, time, sys
RS="\x1e"
def frame(payload, op=0x1):
    b=payload.encode() if isinstance(payload,str) else payload
    h=bytes([0x80|op]); n=len(b)
    h+= bytes([n]) if n<=125 else bytes([126])+struct.pack(">H",n)
    return h+b
def read_frame(c):
    h=c.recv(2)
    if len(h)<2: return None,None
    op=h[0]&0xF; ln=h[1]&0x7F; masked=h[1]&0x80
    if ln==126: ln=struct.unpack(">H",c.recv(2))[0]
    mask=c.recv(4) if masked else b""
    d=b""
    while len(d)<ln: d+=c.recv(ln-len(d))
    if masked: d=bytes(x^mask[i%4] for i,x in enumerate(d))
    return op,d
def handle(c):
    req=b""
    while b"\r\n\r\n" not in req: req+=c.recv(4096)
    head=req.decode(); print("MOCK req:", head.split("\r\n")[0], "| headers:", [l.split(":")[0] for l in head.split("\r\n")[1:] if l])
    key=[l.split(":",1)[1].strip() for l in head.split("\r\n") if l.lower().startswith("sec-websocket-key")][0]
    acc=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    c.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n"%acc).encode())
    op,d=read_frame(c); print("MOCK handshake:", d)
    hs=json.loads(d.decode().split(RS)[0])
    if hs.get("version",1)>2: c.sendall(frame(json.dumps({"error":"The server does not support version %d"%hs["version"]})+RS)); c.close(); return
    c.sendall(frame("{}"+RS))
    t_end=time.time()+2.0; c.settimeout(0.2)
    while time.time()<t_end:
        try: op,d=read_frame(c)
        except socket.timeout: continue
        if op is None: return
        for rec in d.decode().split(RS):
            if not rec: continue
            m=json.loads(rec); print("MOCK got:", m)
            if m.get("type")==1:
                c.sendall(frame(json.dumps({"type":3,"invocationId":m["invocationId"]})+RS))
                if m["target"]=="SubscribeTrades":
                    c.sendall(frame(json.dumps({"type":1,"target":"GatewayUserTrade","arguments":[{"id":1,"price":20000.25}]})+RS))
    c.sendall(frame(json.dumps({"type":6})+RS))
    c.sendall(frame(json.dumps({"type":7,"error":None,"allowReconnect":True})+RS))
    c.sendall(frame(struct.pack(">H",1000)+b"mock bye",0x8))
    time.sleep(0.3); c.close()
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",int(sys.argv[1]))); s.listen(5)
print("MOCK listening", sys.argv[1], flush=True)
while True:
    c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()

#!/usr/bin/env python3
"""Dark-Mode-Spiegel für prophos.html (DARK-FUNDAMENT, 18.10.2026).

Liest die beiden <style>-Blöcke, sammelt jede Farb-Deklaration und schreibt sie
als Kopie unter :where(html[data-theme="dark"]) neu — gleiche Spezifität, gleiche
Reihenfolge, gleiches !important, gleiche @media-Hülle, nur die Farbe umgerechnet.
Weil alle Kopien NACH allen Originalen stehen, spiegelt sich die Kaskade 1:1;
der helle Modus bleibt unberührt (kein Original wird angefasst).

Aufruf: python3 .claude/dark-spiegel.py prophos.html  → ersetzt den Block zwischen den Markern.
"""
import re, sys, colorsys

START = '/* ==== DARK-SPIEGEL (generiert) ==== */'
END = '/* ==== /DARK-SPIEGEL ==== */'
DARK = ':where([data-theme=dark])'

# ---------------------------------------------------------------- CSS-Parser
def strip_comments(s):
    return re.sub(r'/\*.*?\*/', '', s, flags=re.S)

def parse(css, ctx=(), out=None):
    """Liefert Liste (ctx, selector, body) in Quellreihenfolge."""
    if out is None: out = []
    i, n = 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j < 0: break
        head = css[i:j].strip()
        # passende schließende Klammer
        d, k = 1, j + 1
        while k < n and d:
            c = css[k]
            if c == '{': d += 1
            elif c == '}': d -= 1
            k += 1
        body = css[j + 1:k - 1]
        # Kopf kann Reste wie ';' von @import/@charset enthalten
        head = head.split(';')[-1].strip()
        if head.startswith('@'):
            low = head.lower()
            if low.startswith(('@media', '@supports', '@container', '@layer')):
                parse(body, ctx + (head,), out)
            # @keyframes, @font-face, @page: nicht spiegeln
        else:
            out.append((ctx, head, body))
        i = k
    return out

def split_top(s, sep):
    parts, d, cur, q = [], 0, '', None
    for c in s:
        if q:
            cur += c
            if c == q: q = None
            continue
        if c in '"\'':
            q = c; cur += c; continue
        if c in '([': d += 1
        elif c in ')]': d -= 1
        if c == sep and d == 0:
            parts.append(cur); cur = ''
        else:
            cur += c
    parts.append(cur)
    return parts

def decls(body):
    res = []
    for p in split_top(body, ';'):
        if ':' not in p: continue
        name, val = p.split(':', 1)
        name = name.strip(); val = val.strip()
        if not name or '{' in name: continue
        imp = False
        if re.search(r'!\s*important\s*$', val, re.I):
            imp = True; val = re.sub(r'!\s*important\s*$', '', val, flags=re.I).strip()
        res.append((name if name.startswith('--') else name.lower(), val, imp))
    return res

# ---------------------------------------------------------------- Spezifität
def spec(sel):
    s = sel
    a = b = c = 0
    # :where(...) zählt nichts
    s = re_sub_func(s, 'where', lambda inner: '')
    # :is/:not/:has: höchste Spezifität der Argumente
    for fn in ('is', 'not', 'has', 'matches'):
        def rep(inner, fn=fn):
            nonlocal a, b, c
            best = max((spec(x) for x in split_top(inner, ',')), default=(0, 0, 0))
            a += best[0]; b += best[1]; c += best[2]
            return ''
        s = re_sub_func(s, fn, rep)
    s = re.sub(r'::?(nth-[a-z-]+)\([^)]*\)', lambda m: (' :%s ' % m.group(1)), s)
    s = re.sub(r'"[^"]*"|\'[^\']*\'', '', s)
    a += len(re.findall(r'#[\w-]+', s))
    b += len(re.findall(r'\.[\w-]+', s))
    b += len(re.findall(r'\[[^\]]*\]', s))
    pe = re.findall(r'::[\w-]+|:(?:before|after|first-line|first-letter)\b', s)
    c += len(pe)
    s2 = re.sub(r'::[\w-]+|:(?:before|after|first-line|first-letter)\b', '', s)
    b += len(re.findall(r':[\w-]+', s2))
    s3 = re.sub(r'#[\w-]+|\.[\w-]+|\[[^\]]*\]|:[\w-]+|::[\w-]+', ' ', s2)
    c += len([t for t in re.findall(r'(?<![\w-])[a-zA-Z][\w-]*', s3)])
    return (a, b, c)

def re_sub_func(s, fn, cb):
    out, i = '', 0
    pat = ':' + fn + '('
    while True:
        j = s.find(pat, i)
        if j < 0: return out + s[i:]
        k, d = j + len(pat), 1
        while k < len(s) and d:
            if s[k] == '(': d += 1
            elif s[k] == ')': d -= 1
            k += 1
        out += s[i:j] + cb(s[j + len(pat):k - 1])
        i = k

# ---------------------------------------------------------------- Farben
NAMED = {'white': (255, 255, 255), 'black': (0, 0, 0)}

def parse_color(tok):
    t = tok.strip().lower()
    if t in NAMED: return NAMED[t] + (1.0,)
    m = re.fullmatch(r'#([0-9a-f]{3,8})', t)
    if m:
        h = m.group(1)
        if len(h) in (3, 4): h = ''.join(x * 2 for x in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = re.fullmatch(r'rgba?\(([^)]*)\)', t)
    if m:
        p = [x for x in re.split(r'[\s,/]+', m.group(1).strip()) if x]
        try:
            r, g, b = (float(x[:-1]) * 2.55 if x.endswith('%') else float(x) for x in p[:3])
            a = 1.0
            if len(p) > 3:
                a = float(p[3][:-1]) / 100 if p[3].endswith('%') else float(p[3])
            return (r, g, b, a)
        except ValueError:
            return None
    return None

def fmt(r, g, b, a=1.0):
    r, g, b = (max(0, min(255, round(x))) for x in (r, g, b))
    if a >= 0.999: return '#%02x%02x%02x' % (r, g, b)
    return 'rgba(%d,%d,%d,%s)' % (r, g, b, ('%.3f' % a).rstrip('0').rstrip('.'))

def hls(r, g, b):
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

def from_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return r * 255, g * 255, b * 255

def neutral(r, g, b):
    return max(r, g, b) - min(r, g, b) < 28

def is_inkish(r, g, b):
    # Prophos-Tinte rgba(16,24,40,…) und reines Schwarz
    return max(r, g, b) < 60 and neutral(r, g, b)

def text_neutral_token(l):
    if l < 0.22: return 'var(--ink)'
    if l < 0.32: return 'var(--ink-2)'
    if l < 0.52: return 'var(--sub)'
    if l < 0.72: return 'var(--sub-2)'
    return None

def lighten(r, g, b, a, minl):
    h, l, s = hls(r, g, b)
    if l >= minl: return None
    nr, ng, nb = from_hls(h, minl, min(s, 0.9))
    return fmt(nr, ng, nb, a)

def map_color(tok, kind):
    """kind: text | bg | border | shadow | custom. None = unverändert."""
    c = parse_color(tok)
    if c is None: return None
    r, g, b, a = c
    h, l, s = hls(r, g, b)
    neu = neutral(r, g, b)
    if kind == 'shadow':
        if is_inkish(r, g, b):
            return fmt(0, 0, 0, min(0.65, a * 2.2 + 0.08))
        if neu and l > 0.9 and a > 0.6:      # weißer Ring als Schatten
            return 'var(--surface)'
        if neu and l > 0.9:                  # weißes Glühen/Inset-Licht
            return fmt(255, 255, 255, a * 0.25)
        return None
    if kind == 'bg':
        if neu and l > 0.85:
            if a < 0.45: return fmt(255, 255, 255, a * 0.12)
            base = 'var(--surface)' if l > 0.975 else ('var(--surface-tint)' if l > 0.9 else 'var(--border)')
            return base if a > 0.97 else 'color-mix(in srgb,%s %d%%,transparent)' % (base, round(a * 100))
        if not neu and l > 0.82:             # Pastell-Fläche → Farbton als dunkler Tint
            nr, ng, nb = from_hls(h, 0.55, min(0.75, max(s, 0.45)))
            return fmt(nr, ng, nb, 0.16 * a)
        if is_inkish(r, g, b):
            if a < 0.3: return fmt(255, 255, 255, a * 0.9)
            if a < 0.999: return fmt(0, 0, 0, min(0.8, a + 0.15))   # Overlay
            return None                      # dunkle Fläche (Toast) bleibt
        if neu and 0.6 < l <= 0.85:          # mittelgraue Flächen (Schalter-Spur, Balken)
            return 'var(--border)' if a > 0.97 else None
        return None
    if kind == 'border':
        if neu and l > 0.97 and a > 0.6: return 'var(--surface)'
        if neu and l > 0.8:
            if a < 0.45: return fmt(255, 255, 255, a * 0.2)
            return 'var(--border-soft)' if l > 0.94 else 'var(--border)'
        if neu and 0.6 < l <= 0.8: return 'var(--border)'
        if not neu and l > 0.8:
            nr, ng, nb = from_hls(h, 0.5, min(0.75, max(s, 0.45)))
            return fmt(nr, ng, nb, 0.4 * a)
        if is_inkish(r, g, b): return fmt(255, 255, 255, min(0.5, a + 0.02))
        if not neu: return lighten(r, g, b, a, 0.55)
        return None
    # text + custom
    if neu:
        if l > 0.8:
            if kind == 'custom' and a > 0.6:  # helle Variable = meist Linie/Fläche
                return 'var(--border)' if l < 0.9 else ('var(--surface-tint)' if l < 0.975 else 'var(--surface)')
            return None                      # weiße Schrift auf Farbe bleibt
        if is_inkish(r, g, b) and a < 0.999:
            return fmt(255, 255, 255, min(1, a + 0.05))
        tk = text_neutral_token(l)
        if tk and a > 0.97: return tk
        if tk: return 'color-mix(in srgb,%s %d%%,transparent)' % (tk, round(a * 100))
        return None
    if l > 0.82 and kind == 'custom':        # Pastell-Variable → Tint
        nr, ng, nb = from_hls(h, 0.55, min(0.75, max(s, 0.45)))
        return fmt(nr, ng, nb, 0.16 * a)
    if l > 0.82:
        return None
    return lighten(r, g, b, a, 0.66 if l < 0.45 else 0.62)

COLOR_TOK = re.compile(r'#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|(?<![\w-])(?:white|black)(?![\w-])')

def map_value(val, kind):
    changed = [False]
    def rep(m):
        n = map_color(m.group(0), kind)
        if n is None or n == m.group(0): return m.group(0)
        changed[0] = True
        return n
    out = COLOR_TOK.sub(rep, val)
    return out, changed[0]

# ---------------------------------------------------------------- Shorthands
SIDES = ('top', 'right', 'bottom', 'left')
COLOR_WORD = re.compile(r'^(#[0-9a-f]{3,8}|rgba?\(.*\)|hsla?\(.*\)|color-mix\(.*\)|oklch\(.*\)|var\(.*\)|transparent|currentcolor|white|black|[a-z]+)$', re.I)
BORDER_STYLES = {'none', 'hidden', 'dotted', 'dashed', 'solid', 'double', 'groove', 'ridge', 'inset', 'outset'}
NON_COLOR_WORDS = BORDER_STYLES | {'thin', 'medium', 'thick', 'inherit', 'initial', 'unset', 'revert',
                                   'auto', 'repeat', 'no-repeat', 'repeat-x', 'repeat-y', 'center', 'top', 'bottom',
                                   'left', 'right', 'fixed', 'scroll', 'local', 'cover', 'contain', 'padding-box',
                                   'border-box', 'content-box', 'text', 'round', 'space'}

def tokens(v):
    return [t for t in split_top(v, ' ') if t.strip()]

def color_of_border(v):
    low = v.strip().lower()
    if low in ('inherit', 'initial', 'unset', 'revert'): return low
    if low in ('none', '0', 'hidden'): return 'currentcolor'
    col = None
    for t in tokens(v):
        tl = t.lower()
        if re.match(r'^-?[\d.]', tl) or tl in NON_COLOR_WORDS or tl.startswith('calc('): continue
        if COLOR_WORD.match(t): col = t
    if col is None:
        # nur Breite/Stil, oder var() mit ganzem Wert → unklar
        if 'var(' in low and not any(x in low for x in BORDER_STYLES): return None
        return 'currentcolor'
    return col

def color_of_background(v):
    low = v.strip().lower()
    if low in ('inherit', 'initial', 'unset', 'revert'): return low
    last = split_top(v, ',')[-1]
    col = None
    for t in tokens(last):
        tl = t.lower()
        if re.match(r'^-?[\d.]', tl) or tl in NON_COLOR_WORDS or tl == '/' or tl.startswith(('url(', 'calc(')) \
           or 'gradient(' in tl or tl == 'none': continue
        if COLOR_WORD.match(t): col = t
    return col or 'transparent'

def longhands(name, val):
    """(longhand, wert, kind) für alles, was Farbe setzt."""
    if name.startswith('--'):
        return [(name, val, 'custom')]
    if name == 'color': return [('color', val, 'text')]
    if name in ('fill', 'stroke', 'caret-color', 'text-decoration-color', 'column-rule-color'):
        return [(name, val, 'text')]
    if name == 'background-color': return [('background-color', val, 'bg')]
    if name == 'background':
        return [('background-color', color_of_background(val), 'bg')]
    if name in ('box-shadow', 'text-shadow'): return [(name, val, 'shadow')]
    if name in ('outline-color',): return [(name, val, 'border')]
    if name == 'outline':
        c = color_of_border(val)
        return [('outline-color', c, 'border')] if c else []
    if name == 'border-color':
        parts = tokens(val)
        if len(parts) == 1: parts = parts * 4
        elif len(parts) == 2: parts = [parts[0], parts[1], parts[0], parts[1]]
        elif len(parts) == 3: parts = [parts[0], parts[1], parts[2], parts[1]]
        return [('border-%s-color' % s, p, 'border') for s, p in zip(SIDES, parts[:4])]
    if name == 'border':
        c = color_of_border(val)
        return [('border-%s-color' % s, c, 'border') for s in SIDES] if c else []
    m = re.fullmatch(r'border-(top|right|bottom|left)(-color)?', name)
    if m:
        c = val if m.group(2) else color_of_border(val)
        return [('border-%s-color' % m.group(1), c, 'border')] if c else []
    if name in ('border-block', 'border-inline', 'border-block-color', 'border-inline-color'):
        c = val if name.endswith('-color') else color_of_border(val)
        if not c: return []
        sides = ('top', 'bottom') if 'block' in name else ('left', 'right')
        return [('border-%s-color' % s, c, 'border') for s in sides]
    if name in ('border-block-start', 'border-block-end', 'border-inline-start', 'border-inline-end'):
        c = color_of_border(val)
        side = {'border-block-start': 'top', 'border-block-end': 'bottom',
                'border-inline-start': 'left', 'border-inline-end': 'right'}[name]
        return [('border-%s-color' % side, c, 'border')] if c else []
    return []

# ---------------------------------------------------------------- Selektor
def dark_sel(sel):
    s = sel.strip()
    if s.startswith(':root'):
        return DARK + s[len(':root'):]
    if re.match(r'html(?![\w-])', s):
        return 'html' + DARK + s[4:]
    return DARK + ' ' + s

SKIP_SEL = re.compile(r'^:root$')   # Haupt-Tokens kommen von Hand

def build(css_blocks):
    rules = []
    for blk in css_blocks:
        rules += parse(strip_comments(blk))
    # Kandidaten: (idx, ctx, sel, spec, longhand, val, kind, imp)
    items = []
    for idx, (ctx, sel, body) in enumerate(rules):
        if 'data-theme' in sel: continue   # Dark-Tokens selbst nicht spiegeln
        ds_ = decls(body)
        # Toast/Tooltip „Tinte + weiße Schrift": var(--ink) wird dunkel hell — die Fläche bleibt dunkel (erhöht)
        weiss = any(n == 'color' and v.strip().lower() in ('#fff', '#ffffff', 'white') for n, v, _ in ds_)
        for name, val, imp in ds_:
            for lh, v, kind in longhands(name, val):
                if weiss and lh == 'background-color' and v.strip() in ('var(--ink)', 'var(--ink-2)'):
                    v, kind = '#101828', 'tinte'
                for one in split_top(sel, ','):
                    one = one.strip()
                    if not one: continue
                    items.append(dict(i=len(items), ctx=ctx, sel=one, sp=spec(one), lh=lh,
                                      val=v, kind=kind, imp=imp, root=(one == ':root')))
    # gemappte Werte
    KEEP_WHITE = re.compile(r'::?(before|after)|knob|thumb|dot|handle|slider|switch|toggle', re.I)
    for it in items:
        if it['root']:
            it['new'], it['ch'] = it['val'], False
        elif it['kind'] == 'bg' and KEEP_WHITE.search(it['sel']) and (parse_color(it['val']) or (0,0,0,0))[:3] == (255,255,255):
            it['new'], it['ch'] = it['val'], False
        elif it['kind'] == 'tinte':
            it['new'], it['ch'] = '#2B3445', True
        else:
            it['new'], it['ch'] = map_value(it['val'], it['kind'])
    # Welche Kopien braucht es? Geänderte immer. Unveränderte nur, wenn sie
    # eine geänderte Deklaration gleicher Spezifität+Wichtigkeit derselben
    # Eigenschaft im Original schlagen (später in der Quelle) — sonst würde
    # die Kopie der früheren sie überholen.
    need = [it['ch'] for it in items]
    first_changed = {}
    for it in items:
        if it['ch']:
            key = (it['lh'], it['sp'], it['imp'])
            first_changed.setdefault(key, it['i'])
    for it in items:
        if not it['ch'] and not it['root']:
            key = (it['lh'], it['sp'], it['imp'])
            if key in first_changed and first_changed[key] < it['i']:
                need[it['i']] = True
    # Ausgabe in Quellreihenfolge, gleiche Hülle zusammenfassen
    out, cur_ctx, cur_sel, buf = [], None, None, []
    def squash(buf):
        d = {}
        order = []
        for x in buf:
            k, v = x.split(':', 1)
            if k not in d: order.append(k)
            else: order.remove(k); order.append(k)
            d[k] = v
        sides = ['border-%s-color' % q for q in SIDES]
        if all(x in d for x in sides) and len({d[x] for x in sides}) == 1:
            # nur zusammenfassen, wenn die vier direkt hintereinander stehen
            idx = [order.index(x) for x in sides]
            if max(idx) - min(idx) == 3:
                pos = min(idx); v = d[sides[0]]
                order = [o for o in order if o not in sides]
                order.insert(pos, 'border-color'); d['border-color'] = v
        return ';'.join('%s:%s' % (k, d[k]) for k in order)
    def flush():
        if cur_sel is not None and buf:
            body = squash(buf)
            sel = dark_sel_cached(cur_sel)
            if out and out[-1][0] == cur_ctx and out[-1][2] == body:
                out[-1] = (cur_ctx, out[-1][1] + ',' + sel, body)
            else:
                out.append((cur_ctx, sel, body))
    cache = {}
    def dark_sel_cached(s):
        if s not in cache: cache[s] = dark_sel(s)
        return cache[s]
    for it in items:
        if not need[it['i']]: continue
        ds = dark_sel_cached(it['sel'])
        if ds is None: continue
        d = '%s:%s%s' % (it['lh'], it['new'], ' !important' if it['imp'] else '')
        if it['ctx'] == cur_ctx and it['sel'] == cur_sel:
            buf.append(d)
        else:
            flush()
            cur_ctx, cur_sel, buf = it['ctx'], it['sel'], [d]
    flush()
    # in At-Rule-Hüllen gruppieren
    lines, open_ctx = [], ()
    for ctx, sel, body in out:
        rule = '%s{%s}' % (sel, body)
        if ctx != open_ctx:
            # gemeinsamen Präfix behalten
            k = 0
            while k < min(len(ctx), len(open_ctx)) and ctx[k] == open_ctx[k]: k += 1
            for _ in range(len(open_ctx) - k): lines.append('}')
            for h in ctx[k:]: lines.append(h + '{')
            open_ctx = ctx
        lines.append(rule)
    for _ in open_ctx: lines.append('}')
    stats = dict(rules=len(rules), items=len(items), changed=sum(1 for i in items if i['ch']),
                 copies=sum(need))
    return '\n'.join(lines), stats

if __name__ == '__main__':
    path = sys.argv[1]
    src = open(path, encoding='utf-8').read()
    # Generierten Block vor dem Lesen herausnehmen
    src_clean = re.sub(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', '', src, flags=re.S)
    blocks = re.findall(r'<style>(.*?)</style>', src_clean, flags=re.S)
    # nur echte Seiten-Styles: der <style> im JS-String (Mail-Vorschau) hat body{…} im Template
    blocks = [b for b in blocks if len(b) > 2000]
    text, st = build(blocks)
    print(st, len(text), file=sys.stderr)
    if '--dry' in sys.argv:
        print(text); sys.exit()
    hinweis = ('/* Dark Mode (Finn 18.10.2026): jede Farb-Deklaration der Styles oben noch einmal unter\n'
               '   :where([data-theme=dark]) — gleiche Spezifität, gleiche Reihenfolge, nur die Farbe umgerechnet. Hell bleibt\n'
               '   unberührt. NICHT von Hand pflegen: neu erzeugen mit  python3 .claude/dark-spiegel.py prophos.html\n'
               '   Neue Regeln bitte gleich mit Tokens (var(--surface), var(--ink), var(--good-ink) …) schreiben. */\n')
    block = START + '\n' + hinweis + text + '\n' + END + '\n'
    # ans Ende des LETZTEN Seiten-<style>
    last = src_clean.rfind('</style>')
    if START in src:
        # an alter Stelle ersetzen
        new = re.sub(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', lambda m: block, src, flags=re.S)
    else:
        new = src_clean[:last] + block + src_clean[last:]
    open(path, 'w', encoding='utf-8').write(new)

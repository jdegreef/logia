import sys, glob, re, os
sys.path.insert(0, os.path.dirname(__file__))
import ccelparas, chunk
ROOT = os.environ.get("LOGIA", "/home/user/logia"); WORK = "calvin-romans"
NUM = re.compile(r'^(\d+)(?:\s*[-–,]\s*(\d+))?\s*\.')
def lead_italic(q):
    """the leading italic run of a paragraph, after an optional bold verse number."""
    parts = [(f, d) for f, d in q['parts'] if d.strip() or f]
    out, seen = [], False
    for f, d in parts:
        if 'b' in f and not seen and re.fullmatch(r'\s*[\d\s,–-]+\.?\s*', d): continue
        if 'i' in f:
            seen = True; out.append(d); continue
        if seen and re.fullmatch(r'[\s.,;:]*', d): out.append(d); continue
        if not seen and re.fullmatch(r'\s*[\d\s,–-]*\.?\s*', d): continue
        break
    return ' '.join(''.join(out).split())
def clean_heading(h):
    h = re.sub(r'^[\d\s,–-]*\.\s*', '', h)
    h = re.sub(r'[,;:]?\s*etc\.?\s*$', '', h).strip()
    h = h.strip(' .,;:')
    return h
order = lambda f: [int(x) if x.isdigit() else x for x in f]
def key(f):
    import scripture
    parts = os.path.basename(f).split('.')[1:3]
    return tuple(scripture.roman(p.upper()) for p in parts)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
units = []
for f in sorted(glob.glob(f'{ROOT}/sources/{WORK}/*.html'), key=key):
    src = os.path.basename(f)
    for q in ccelparas.paras(f):
        if q['table'] or not q['text'] or not q['div']: continue
        if q['cls'].startswith(('3rdLevel', 'HDG')): continue        # the book's closing line
        if q['text'].startswith('The Epistle closes, as we see, with praise'):
            # Calvin's comment on the doxology (16:25-27) has no lemma; CCEL leaves it under 16:21
            units.append({'ch': 16, 'v1': 25, 'v2': 27, 'heading': '', 'paras': [q['text']], 'src': src})
            continue
        if units and (units[-1]['ch'], units[-1]['v1']) == (16, 25):
            units[-1]['paras'].append(q['text']); continue
        ch, dv = map(int, q['div'].split('.')[-2:])
        m = NUM.match(q['text'])
        h = lead_italic(q)
        starts = q['cls'] != 'SCRIPTURE' and (m or (h and q['text'].startswith(h[:10])))
        moved = units and (units[-1]['src'] != src or units[-1]['ch'] != ch or dv > units[-1]['v2'])
        if starts or not units or moved:
            v1 = int(m[1]) if m else dv
            v2 = int(m[2]) if m and m[2] else v1
            if m and int(m[1]) != dv and not units: pass
            units.append({'ch': ch, 'v1': v1, 'v2': v2, 'heading': clean_heading(h), 'paras': [], 'src': src})
        units[-1]['paras'].append(q['text'])
data = chunk.build(WORK, 'ROM', units)
chunk.dump(f'{ROOT}/library/comments/{WORK}/ROM.json', data)
E = data['entries']; L = [len(e['text'].split()) for e in E]
print(len(units), len(E), sum(L), min(L), max(L), sorted(L)[len(L)//2])

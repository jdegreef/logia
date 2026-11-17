import sys, glob, re, os
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.environ.get("LOGIA", "/home/user/logia"), "scripts"))
import ccelparas, chunk, scripture
ROOT = os.environ.get("LOGIA", "/home/user/logia"); WORK = "henry-romans"
DIV = re.compile(r'Bible:Rom\.(\d+)\.(\d+)(?:-Rom\.(\d+)\.(\d+))?$')
# a verse mark near the start of a point: "(v. 1)", "v. 3, 4", "v. 11-15", "ver. 16"
VMARK = re.compile(r'(?<![A-Za-z]\. )(?<!ch\. )(?<!chap\. )\b(?:v|ver|vv)\.\s*(\d+)(?:\s*(?:-|–|,| to )\s*(\d+))?')
ENUM = re.compile(r'^(?:[IVXL]+\.|\d+\.|\(\d+\.\)|\[\d+\.\]|\d+\.\)|[a-z]\.)\s+')
def heading(text):
    t = ENUM.sub('', text)
    m = re.match(r'(.{3,90}?)(?=\s*\(v\.|\s*,\s*v\.|\s*;\s*v\.|[:.;!?]|\s+v\.\s*\d|—)', t)
    h = m[1].strip(' ,') if m else ''
    return h if len(h.split()) <= 14 else ''
def files():
    return sorted(glob.glob(f'{ROOT}/sources/{WORK}/*.html'), key=lambda f: scripture.roman(f.split('.')[-2].upper()))
units = []
for f in files():
    src = os.path.basename(f)
    for q in ccelparas.paras(f):
        if not q['text'] or not q['div'] or q['cls'] in ('passage', 'h4', 'h3', 'h2', 'intro'):
            continue
        m = DIV.match(q['div']); ch, a = int(m[1]), int(m[2]); ch2, b = int(m[3] or ch), int(m[4] or a)
        assert ch == ch2, q['div']
        sec = (ch, a, b)
        prev = units[-1] if units else None
        if not prev or prev['sec'] != sec:
            cur_v = (a, b) if a == b else (a, a) if False else (a, b)
        else:
            cur_v = (prev['v1'], prev['v2'])
        mk = None
        for x in VMARK.finditer(q['text'][:160]):
            v1 = int(x[1]); v2 = int(x[2] or x[1])
            if a <= v1 <= v2 <= b:
                mk = (v1, v2); break
        if mk: cur_v = mk
        elif re.match(r'[IVXL]+\.\s', q['text']): cur_v = (a, b)     # a main point naming no verse: on the section
        if prev and prev['sec'] == sec and (prev['v1'], prev['v2']) == cur_v and not mk:
            prev['paras'].append(q['text']); continue
        units.append({'ch': ch, 'v1': cur_v[0], 'v2': cur_v[1], 'heading': heading(q['text']) if mk else '',
                      'paras': [q['text']], 'src': src, 'sec': sec})
# a lead-in ("In this paragraph we have,") joins the point after it, in the same section
joined = []
for u in units:
    if joined and joined[-1]['sec'] == u['sec'] and len(joined[-1]['paras']) == 1 \
            and chunk.wc(joined[-1]['paras'][0]) < 25 and not joined[-1]['heading']:
        lead = joined.pop(); u = dict(u, paras=lead['paras'] + u['paras'])
    joined.append(u)
units = joined
# the Open Word Bible text has no Romans 16:25-27, so the comment on it has no verse to stand beside

data = chunk.build(WORK, 'ROM', units)
chunk.dump(f'{ROOT}/library/comments/{WORK}/ROM.json', data)
E = data['entries']; L = [len(e['text'].split()) for e in E]
print(len(units), len(E), sum(L), min(L), max(L), sorted(L)[len(L)//2], len({e['start'] for e in E}))

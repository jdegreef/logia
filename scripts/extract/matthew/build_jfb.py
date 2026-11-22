"""build_jfb.py: cut Jamieson-Fausset-Brown (David Brown) on Matthew from its CCEL pages
into library/comments/jfb-matthew/MAT.json. Run from the repository root."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'romans'))
import ccelparas, chunk
WORK, SRC = 'jfb-matthew', 'sources/jfb-matthew'
NUM = re.compile(r'^(\d+)(?:\s*[-,–]\s*(\d+))?(?:\s*,\s*(\d+))*\.\s')
SUMMARY = re.compile(r'^Mt (\d+):(\d+)(?:\s*[-,]\s*(\d+))?')
SUB = re.compile(r'^(?!\d)[^()]{3,240}?\((?:see )?Mt (\d+):(\d+)(?:\s*[-,]\s*(\d+))?[^()]*\)[.:]')
OTHER = re.compile(r'^(Lu|Mr|Joh|Ac) \d+:\d+(?:-\d+)?:$')
INTRO_OTHER = re.compile(r'^(The third Gospel|Luke adds|Mark adds|Luke here adds|Mark here adds)')
RETURN = re.compile(r'^\(We now return to')
def pages():
    def key(p):
        r = p.rsplit('.', 2)[-2]
        v = {'i': 1, 'v': 5, 'x': 10}; n = 0
        for a, b in zip(r, r[1:] + ' '):
            n += -v[a] if v.get(b, 0) > v[a] else v[a]
        return n
    return sorted(glob.glob(f'{SRC}/*.html'), key=key)
log = []
def run():
    units = []; cur = None
    for path in pages():
        src = os.path.basename(path); ch = None; other = False; cur = None; lastv = 0
        for p in ccelparas.paras(path):
            t = p['text']
            m = re.match(r'^CHAPTERS? (\d+)', t)
            if m and p['cls'] == 'Center':
                ch = int(m[1]); continue
            if RETURN.match(t):
                other = False; continue
            if OTHER.match(t) or INTRO_OTHER.search(t) and not SUMMARY.match(t):
                other = True; log.append(('other', src, t[:80])); continue
            m = SUMMARY.match(t) or SUB.match(t)
            if m:
                other = False; ch = int(m[1]); a = int(m[2]); b = int(m[3] or a)
                if re.match(r'^Mt \d+:\d+-\d+:\d+', t):   # a section running into the next chapter
                    b = json.load(open(f'bible/owb/en/MAT.{ch}.json'))['verses'][-1]
                cur = {'ch': ch, 'v1': a, 'v2': b, 'heading': '', 'paras': [t], 'src': src}
                units.append(cur); continue
            m = NUM.match(t)
            if m and not other or (m and other and int(m[1]) > lastv and False):
                nums = [int(x) for x in re.findall(r'\d+', m[0])]
                a, b = nums[0], nums[-1]
                if a < lastv: log.append(('backwards', src, ch, a, lastv, t[:60]))
                lastv = b
                cur = {'ch': ch, 'v1': a, 'v2': b, 'heading': '', 'paras': [t], 'src': src}
                units.append(cur); continue
            if other:
                log.append(('skip-other', src, t[:80])); continue
            if cur is None:
                log.append(('no-unit', src, t[:80])); 
                if src == 'jfb.xi.i.vi.html' and len(t) > 200:
                    cur = {'ch': 5, 'v1': 1, 'v2': 1, 'heading': '', 'paras': [t], 'src': src}
                    units.append(cur)
                continue
            cur['paras'].append(t)
    return units
if __name__ == '__main__':
    units = run()
    for l in log: print(*l)
    data = chunk.build(WORK, 'MAT', units)
    chunk.dump(f'library/comments/{WORK}/MAT.json', data)
    print(len(data['entries']), 'entries')

import sys, re, os
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.environ.get("LOGIA", "/home/user/logia"), "scripts"))
import ccelparas, chunk, chrys_cut, scripture
ROOT = os.environ.get("LOGIA", "/home/user/logia"); WORK = "chrysostom-romans"
HEAD = re.compile(r'^Homily\s+([IVXLC]+)\.$')
REFH = re.compile(r'^Rom\.\s+([IVXL]+)\.\s+(\d+)(?:\s*(?:[–-]|,\s*)(\d+))?$')
MARK = re.compile(r'^(?:Chap\.\s+([ivxl]+)\.\s+ver|Ver)\.\s+(\d+)(?:\s*(?:[–-]|,\s*)(\d+))?\.')
# Chrysostom's text has the closing doxology (now Romans 16:25-27) after 14:23, as many Greek
# manuscripts do; the homily on it is headed "Rom. XIV. 25-27".
MOVED = {(14, 25): 16}
# Homily VI prints "Ver. 12." over Romans 2:28 ("For he is not a Jew which is one outwardly"), between ver. 27 and 29.
MISPRINT = {("npnf111.vii.viii.html", 12): 28}
units = []
for f in chrys_cut.files():
    src = os.path.basename(f)
    ps, cut = chrys_cut.homily(f)
    if cut:
        i, j = cut
        ss = chunk.sentences(ps[i])
        ps = ps[:i] + ([' '.join(ss[:j])] if j else [])
    title = ref = None; body = []
    for k, p in enumerate(ps):
        if k < 3 and HEAD.match(p): title = p; continue
        if k < 3 and REFH.match(p): ref = p; continue
        body.append(p)
    m = REFH.match(ref)
    ch = scripture.roman(m[1]); v1 = int(m[2]); v2 = int(m[3] or m[2])
    ch = MOVED.get((ch, v1), ch)
    heading = f"{title} {ref}"
    cur = {'ch': ch, 'v1': v1, 'v2': v2, 'heading': heading, 'paras': [], 'src': src}
    homily_units = [cur]
    for p in body:
        mk = MARK.match(p)
        if mk:
            a = int(mk[2]); b = int(mk[3] or mk[2])
            a = b = MISPRINT.get((src, a), a) if a == b else a
            if mk[1]: ch = scripture.roman(mk[1])     # every change of chapter is printed "Chap. v. ver. 1."
            cur = {'ch': ch, 'v1': a, 'v2': b, 'heading': heading, 'paras': [], 'src': src}
            homily_units.append(cur)
        cur['paras'].append(p)
    # the Open Word Bible text has no Romans 16:25-27 (its pinned SBLGNT data lacks the doxology),
    # so the comment on it has no verse to stand beside; it stays in the whole homily (library/texts/)
    units += homily_units
data = chunk.build(WORK, 'ROM', units)
chunk.dump(f'{ROOT}/library/comments/{WORK}/ROM.json', data)
E = data['entries']; L = [len(e['text'].split()) for e in E]
print(len(units), len(E), sum(L), min(L), max(L), sorted(L)[len(L)//2], len({e['start'] for e in E}))

"""build_wesley.py: cut Wesley's Explanatory Notes on Matthew from its CCEL pages into
library/comments/wesley-matthew/MAT.json, one excerpt per verse note. Run from the repository root."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'romans'))
import ccelparas, chunk
WORK, SRC = 'wesley-matthew', 'sources/wesley-matthew'
NUM = re.compile(r'^(\d+)((?:\s*[-,]\s*\d+)*)\.\s')
ROMAN = {'i': 1, 'v': 5, 'x': 10, 'l': 50}
def roman(r):
    r = r.lower(); n = 0
    for a, b in zip(r, r[1:] + ' '):
        n += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return n
def last_verse(ch):
    return json.load(open(f'bible/owb/en/MAT.{ch}.json'))['verses'][-1]
def heading(t):
    m = re.match(r'^\d+(?:\s*[-,]\s*\d+)*\.\s+(.*?)\s+-(?:\s|(?=[A-Z]))', t)
    if not m or re.search(r'[()]|[.:;!?] ', m[1]) or ' -- ' in m[1]:
        return ''
    return m[1]
def run():
    units = []
    pages = sorted(glob.glob(f'{SRC}/*.html'), key=lambda p: roman(p.rsplit('.', 2)[-2]))
    for path in pages:
        src = os.path.basename(path); ch = None; cur = None
        for p in ccelparas.paras(path):
            t = p['text']
            if p['cls'] == 'h3':
                ch = roman(t.strip()); cur = None; continue
            m = NUM.match(t)
            nums = [int(x) for x in re.findall(r'\d+', m[0])] if m else []
            if m and cur and cur['ch'] == ch and nums[0] < cur['v1']:
                # a numbered point inside a note (the petitions of the Lord's Prayer), not a verse
                print('point', ch, cur['v1'], t[:50]); cur['paras'].append(t); continue
            if m and not p['cls'].startswith('List'):
                if (ch, nums[0]) == (6, 10) and t.startswith('10. Our Father'):
                    nums = [9, 13]   # CCEL numbers it 10; the note and its points cover the prayer, 6:9-13
                cur = {'ch': ch, 'v1': nums[0], 'v2': nums[-1], 'heading': heading(t), 'paras': [t], 'src': src}
                units.append(cur); continue
            if cur is None:   # an outline that opens the chapter, on the whole chapter
                cur = {'ch': ch, 'v1': 1, 'v2': last_verse(ch), 'heading': '', 'paras': [t], 'src': src}
                units.append(cur); print('outline', ch, t[:60]); continue
            cur['paras'].append(t)
    return units
if __name__ == '__main__':
    units = run()
    # one excerpt per note, whole: no packing or merging
    entries, seen = [], {}
    for u in units:
        key = f"MAT.{u['ch']}.{u['v1']}" + (f"-{u['v2']}" if u['v2'] != u['v1'] else '')
        seen[key] = seen.get(key, 0) + 1
        entries.append({'id': f"{WORK}.{key}.{seen[key]}", 'start': f"MAT.{u['ch']}.{u['v1']}",
                        'end': f"MAT.{u['ch']}.{u['v2']}", 'heading': u['heading'],
                        'text': '\n\n'.join(u['paras']), 'sources': [u['src']]})
    entries.sort(key=lambda e: (int(e['start'].split('.')[1]), int(e['start'].split('.')[2])))
    chunk.dump(f'library/comments/{WORK}/MAT.json', {'work': WORK, 'book': 'MAT', 'entries': entries})
    w = [len(e['text'].split()) for e in entries]
    print(len(entries), 'entries', sum(w), 'words, longest', max(w))

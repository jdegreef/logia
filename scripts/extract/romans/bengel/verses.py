"""Stage 2: paragraphs -> (chapter, v1, v2, [paragraphs]) by the CHAPTER heads and Bengel's verse numbers."""
import json, re, sys

WT = '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/wt-bengel'
COUNTS = {}
for c in range(1, 17):
    COUNTS[c] = json.load(open(f'{WT}/bible/owb/en/ROM.{c}.json'))['verses'][-1]

CH = re.compile(r'^CHAPT\w+\s+\S+\s*$')
VS = re.compile(r'^(?:V\.\s+)?(\d{1,2}|\d\s\d)(?:\s*[,—–-]\s*(\d{1,2})|\.\s+(\d{1,2})(?=\.\s))?\s*[.-](?:\d|\')?\s+')


def main():
    paras = json.load(open(sys.argv[1]))['paras']
    units, ch, cur, log = [], 0, 0, []
    # split a paragraph where a verse number was run into the text before it
    split = []
    for p in paras:
        p = re.sub(r'^G\.\s', '6. ', p)
        p = re.sub(r'^1\. (Eire, or\))', r'7. \1', p)
        p = re.sub(r'^(19) (?=\'Tvazori)', r'\1. ', p)
        p = re.sub(r'^(?=Uapidodri, was delivered\))', '25. ', p)     # the OCR lost the verse number of Rom. 4:25
        split.append(p)
    paras = split
    def runin(p, cur):
        for m in re.finditer(r'(?<=[.)\]]) (\d{1,2})[.\-] (?![—;,\d(\[])(?=[^()]{1,80}\))', p):
            n = int(m[1])
            prev = p[:m.start()].split()[-1].lower() if p[:m.start()].split() else ''
            if n not in (cur + 1, cur + 2) or m.start() < 20:
                continue
            if re.fullmatch(r'[ivxlc]+\.|ver\.|vv?\.|ch\.|comp\.|cf\.|p\.|[a-z]{1,5}\.', prev) and not prev in ('grace.',):
                continue
            return m
        return None
    queue = list(paras)
    while queue:
        p = queue.pop(0)
        if CH.match(p):
            ch += 1; cur = 0; continue
        if units and ch:
            m = runin(p, max(cur, units[-1]['v2']) if units[-1]['ch'] == ch else cur)
            if m:
                log.append(f'RUNIN {ch}:{m[1]} ...{p[max(0, m.start() - 40):m.end() + 40]}')
                queue.insert(0, m[1] + '. ' + p[m.end():].lstrip()); p = p[:m.start()]
        m = VS.match(p)
        if m and ch:
            v1 = int(m[1].replace(' ', '')); v2 = int(m[2] or m[3] or v1)
            if cur - 3 <= v1 <= cur + 9 and v2 >= v1 and v2 <= COUNTS.get(ch, 99) + 3:
                units.append({'ch': ch, 'v1': v1, 'v2': v2, 'paras': [p[m.end():]]})
                cur = max(cur, v1)
                continue
            log.append(f'REJECT {ch}:{cur} {p[:80]}')
        if not units:
            log.append('PRE ' + p[:80]); continue
        units[-1]['paras'].append(p)
    json.dump({'units': units, 'log': log, 'counts': COUNTS}, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
    print(ch, 'chapters', len(units), 'verse units')
    for x in log:
        print(x)
    for c in range(1, 17):
        vs = [(u['v1'], u['v2']) for u in units if u['ch'] == c]
        print(c, COUNTS.get(c), ' '.join(f'{a}' if a == b else f'{a}-{b}' for a, b in vs))


main()

import sys, re, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/tools'); sys.path.insert(0, HERE)
import marks, greek, chunk, garble
ROOT = '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/wt-godet'
WORK = 'godet-romans'
CH_LEN = [0, 32, 29, 31, 25, 21, 23, 25, 39, 33, 21, 36, 21, 14, 23, 33, 27]
OVERRIDE = json.load(open(os.path.join(HERE, 'override.json'))) if os.path.exists(os.path.join(HERE, 'override.json')) else {}
DEBUG = '-v' in sys.argv

def parse_nums(g, ch):
    s = g.replace("'", '').replace('^', ',').replace('l', '1').replace('I', '1').replace('O', '0').replace('o', '5')
    nums = [int(x) for x in re.findall(r'\d+', s)]
    out = []
    for n in nums:
        if ch and n > CH_LEN[ch] and n >= 100: n = n // 10          # 306 = 30b
        out.append(n)
    return out

def cut_greek(p, log, lemma=False):
    """garbled Greek out, each cut marked ' ... '. lemma: p opens with Godet's rendering of the verse
    (italic, which the OCR garbles as English), kept whole but for the garbled words."""
    head = ''
    if lemma:
        m = re.search(r'\s—\s', p)
        if m and m.start() < 1500:
            head, p = p[:m.start()], p[m.start():]
    if head:
        head = cut_greek_inline(head, log)
    p = garble.strip_greek(p, log) if not head else garble.strip_greek(p, log)
    return (head + ' ' + cut_sents(p, log)).strip() if head else cut_sents(p, log)

def cut_greek_inline(p, log):
    return cut_sents(p, log, drop=False)

def cut_sents(p, log, drop=True):
    sents = chunk.sentences(p)
    res = []
    for snt in sents:
        toks = snt.split()
        flags = [greek.is_greek(t) for t in toks]
        for k, t in enumerate(toks):          # iv (the Greek preposition) where it is not a chapter number
            if re.fullmatch(r'\(?iv[,;:)]?', t) and not (k + 1 < len(toks) and re.match(r'\d', toks[k + 1])):
                flags[k] = True
        words = [t for t in toks if re.search(r'[A-Za-z]', t)]
        nbad = sum(flags)
        if drop and words and (nbad / len(words) >= 0.45 or nbad >= 8) and not marks.MARK.match(snt):
            log.append('SENT: ' + snt); res.append('...'); continue
        out = []; i = 0
        while i < len(toks):
            if flags[i]:
                j = i
                while j < len(toks) and (flags[j] or (j + 1 < len(toks) and flags[j + 1] and len(greek.core(toks[j])) <= 2)
                                          or not re.search(r'[A-Za-z0-9]', toks[j])):
                    j += 1
                log.append('CUT: ' + ' '.join(toks[i:j]))
                # keep sentence-ending punctuation of the last cut token
                tail = re.search(r'[.?!:;]["”’]?$', toks[j - 1])
                out.append('...' + ('' if not tail else ''))
                i = j; continue
            out.append(toks[i]); i += 1
        x = ' '.join(out)
        res.append(x)
    t = ' '.join(res)
    # tidy the marks around a cut
    t = re.sub(r'[\(\[\{]\s*(?:\.\.\.\s*)+[\)\]\}]', '...', t)
    t = re.sub(r'(?:\s*\.\.\.)+', ' ...', t)
    t = re.sub(r'\.\.\.\s*[,;:]', '...', t)
    t = re.sub(r'\s*\.\.\.\s*', ' ... ', t).strip()
    t = re.sub(r'^\.\.\.\s*', '', t); t = re.sub(r'\s*\.\.\.$', '', t)
    return t

def tidy(p):
    p = re.sub(r'\^+', '', p)                         # footnote markers and the OCR's "—^"
    p = re.sub(r'(?<=\w)\*+(?=[\s,.;:]|$)', '', p)     # a footnote star after a word
    p = re.sub(r'\s+\*+\s+', ' ', p)
    p = re.sub(r'(?<=[\w,.;:])\s?[†‡]+', '', p)
    p = re.sub(r'\s{2,}', ' ', p).strip()
    return p

def heading_of(s):
    m = re.match(r'^\s*(?:[\*"“\'‘^]{1,3})\s*(.+?)(?:["”\'’*]{1,2}\s*—|["”]\s*$)', s)
    if not m: return ''
    h = m[1].strip().rstrip('.,;:!?*\'"” ')
    if len(h.split()) > 12 or any(greek.is_greek(t) for t in h.split()): return ''
    return tidy(h)

def main():
    items = marks.all_items()
    units = []; seq = []
    cur = None; pending = None     # pending: intro paragraphs waiting for their chapter
    ch = 0; prev = 0; vol = None
    glog = []
    for f, k, s in items:
        if k == 'log':
            continue
        if f != vol:
            vol = f; ch = 1 if '01' in f else 7; prev = 0
        src = f
        if k == 'struct':
            cur = None
            m = re.search(r'PASS\s?AGE\s*[\(Q][^)]*?(\d+)\s*[-—,]\s*(\d+)\)', s)
            if 'PASS' in s:
                pending = {'hdr': s, 'v': (int(m[1]), int(m[2])) if m else None, 'paras': [], 'src': src}
            else:
                pending = None
            if DEBUG: print('STRUCT', s[:60])
            continue
        if k in ('caps', 'title'):
            continue
        if k == 'range':
            n = parse_nums(re.sub(r'^\d\.\s*', '', s.split(':')[-1]), ch)
            v1, v2 = n[0], n[-1]
            if v1 < prev and v1 <= 3 and prev >= CH_LEN[ch] - 12: ch += 1
            if pending and pending['paras']:
                flush_pending(units, pending, ch, v1)
            pending = {'hdr': s, 'v': (v1, v2), 'paras': [], 'src': src, 'range': True}
            cur = None; prev = v1
            if DEBUG: print('RANGE', ch, v1, v2, s)
            continue
        mk = marks.MARK.match(s)
        if mk:
            key = s[:40]
            if key in OVERRIDE:
                v1, v2 = OVERRIDE[key]
            else:
                n = parse_nums(mk[1], ch); v1, v2 = n[0], n[-1]
            if v1 < prev and v1 <= 3 and prev >= CH_LEN[ch] - 12: ch += 1
            if v2 < v1: v2 = v1
            if v1 < prev and DEBUG: print('  BACK', prev, '->', v1, s[:60])
            if pending:
                flush_pending(units, pending, ch, v1)
                pending = None
            if v2 > CH_LEN[ch] or v1 > CH_LEN[ch]: print('PAST END', ch, v1, v2, s[:60])
            body = s
            h = heading_of(s[mk.end():])
            cur = {'ch': ch, 'v1': v1, 'v2': v2, 'heading': h, 'paras': [body], 'src': src}
            units.append(cur); prev = v1
            seq.append((ch, v1, v2))
            if DEBUG: print('MARK', ch, v1, v2, '|', h[:50], '|', s[:50])
            continue
        if pending is not None:
            pending['paras'].append(s)
        elif cur is not None:
            cur['paras'].append(s)
    # text processing
    for u in units:
        out = []
        for k, p in enumerate(u['paras']):
            q = tidy(cut_greek(p, glog, lemma=(k == 0 and not u.get('intro') and bool(marks.MARK.match(p)))))
            if len(q.split()) >= 3 and re.search(r'[a-z]{3}', q): out.append(q)
        u['paras'] = out
    # a short introduction to a passage goes on the passage's first verse(s), with the note that follows it
    merged = []
    for u in units:
        p = merged[-1] if merged else None
        if p and p.get('intro') and p['ch'] == u['ch'] and p['v1'] == u['v1'] and len(' '.join(p['paras']).split()) < 60 and not u.get('intro'):
            merged[-1] = dict(u, paras=p['paras'] + u['paras']); continue
        merged.append(u)
    units = merged
    for u in units:
        u['v2'] = min(u['v2'], CH_LEN[u['ch']])
        u['src'] = u['src']
    data = chunk.build(WORK, 'ROM', units)
    # a short piece cut off the end of a paragraph joins the piece before it again
    E0 = data['entries']; E1 = []
    for e in E0:
        p = E1[-1] if E1 else None
        if p and (p['start'], p['end']) == (e['start'], e['end']) and e['text'].startswith('... ') and p['text'].endswith(' ...') \
                and len(e['text'].split()) < 60 and len(p['text'].split()) + len(e['text'].split()) <= 430:
            p['text'] = p['text'][:-4] + ' ' + e['text'][4:]; continue
        E1.append(e)
    cnt = collections.Counter()
    for e in E1:
        key = e['id'].rsplit('.', 1)[0]; cnt[key] += 1; e['id'] = f"{key}.{cnt[key]}"
    data['entries'] = E1
    chunk.dump(f'{ROOT}/library/comments/{WORK}/ROM.json', data)
    open(os.path.join(HERE, 'greek.log'), 'w').write('\n'.join(glog))
    E = data['entries']; L = [len(e['text'].split()) for e in E]
    print(len(units), len(E), sum(L), min(L), max(L), sorted(L)[len(L) // 2])
    print(sorted(collections.Counter(int(e['start'].split('.')[1]) for e in E).items()))

def flush_pending(units, pending, ch, v_next):
    if not pending['paras']: return
    if pending.get('v'):
        a, b = pending['v']
        if not (1 <= a <= v_next and a <= b <= CH_LEN[ch]): a, b = v_next, v_next
        if a > v_next: a = v_next
    else:
        a = b = v_next
    units.append({'ch': ch, 'v1': a, 'v2': b, 'heading': '', 'paras': pending['paras'], 'src': pending['src'], 'intro': True})
    pending['paras'] = []

main()

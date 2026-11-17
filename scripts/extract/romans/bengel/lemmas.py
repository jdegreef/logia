"""Stage 3: each verse note -> lemma units (gloss as printed, note), the garbled Greek left out."""
import json, re, sys
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/agent-bengel')
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/tools')
import chunk  # noqa: E402
from greek import greekish, noise, english, core, rare_short  # noqa: E402

CLOSE = re.compile(r'[)}](?=\s|[,.;:\]]\s|$)')


def eng_share(s):
    toks = [core(t) for t in s.split()]
    toks = [t for t in toks if re.search(r'[A-Za-z]', t)]
    if not toks:
        return 0
    return sum(1 for t in toks if not greekish(t)) / len(toks)


def split_lemma(L):
    """L: text of a lemma before its ')' -> (greek part, gloss) or None if it is not a lemma."""
    toks = L.split()
    if not toks:
        return None
    if not noise(toks[0]) and not greekish(toks[0]) and not rare_short(toks[0]):
        return None
    # the gloss follows the first comma after which the words are English
    for m in re.finditer(r',\s*', L):
        left, right = L[:m.start()], L[m.end():]
        lt = [t for t in left.split() if re.search(r'[A-Za-z]', t)]
        foreign = [t for t in lt if noise(t) or not english(re.sub(r'[^A-Za-z]', '', t))]
        if len(right.split()) > 12 or ';' in right or re.search(r'[.?!] [A-Z0-9]', right) or ('—' in right and '—' not in left):
            continue
        if right and eng_share(right) >= 0.9 and not greekish(right.split()[0]) and lt and len(foreign) * 2 >= len(lt):
            return left, right.strip()
    if all(noise(t) or not re.search(r'[A-Za-z]', t) for t in toks) or eng_share(L) <= 0.34:
        return L, ''
    return None


def find_lemmas(text):
    """positions (start, greek_end, close_end, gloss) of the lemmas in a verse note."""
    out = []
    opens = [0] + [m.end() for m in re.finditer(r'—|(?<=[.;\])])\s+(?=\S+\s*\S*\s*[,)}])', text)]
    for b in opens:
        while b < len(text) and text[b] in ' \n':
            b += 1
        seg = text[b:b + 140]
        m = CLOSE.search(seg)
        if not m:
            continue
        L = seg[:m.start()]
        if '(' in ' '.join(t for t in L.split() if not greekish(t)) or '\n\n' in L:
            continue
        sp = split_lemma(L)
        if not sp:
            continue
        g, gloss = sp
        end = b + m.end()
        if not gloss:
            # "2opa) to the wise)" : the gloss after the Greek, closed again
            n = re.match(r'\s*([^()\[\].;:—]{1,40}?)[)}]', text[end:])
            if n and eng_share(n[1]) >= 0.99 and len(n[1].split()) <= 6:
                gloss = n[1].strip(); end += n.end()
        if out and b < out[-1][2]:
            continue
        out.append((b, b + len(g), end, gloss))
    return out


def scrub(s, log):
    """leave out runs of garbled Greek, marking the gap ' ... '."""
    toks = re.split(r'(\s+)', s)
    words = toks[0::2]
    bad = [greekish(w) for w in words]
    # a short unknown token next to a garbled one belongs to it
    for _ in range(3):
        for i, w in enumerate(words):
            if not bad[i] and (noise(w) or rare_short(w)) and ((i and bad[i - 1]) or (i + 1 < len(words) and bad[i + 1])):
                bad[i] = True
    for i, w in enumerate(words):
        if not bad[i] and re.fullmatch(r'[\'"‘’“”`]+[,;.]?', w) and ((i and bad[i - 1]) or (i + 1 < len(words) and bad[i + 1])):
            bad[i] = True
    # dashes, '&' and lone punctuation between garbled words go with them
    for i, w in enumerate(words):
        if not bad[i] and re.fullmatch(r'[—\-&;,:.]+', w) and i and bad[i - 1] and i + 1 < len(words) and bad[i + 1]:
            bad[i] = True
    out, run = [], []
    for i, w in enumerate(words):
        if bad[i]:
            run.append(w); continue
        if run:
            log.append(' '.join(run)); out.append('...'); run = []
        out.append(w)
    if run:
        log.append(' '.join(run)); out.append('...')
    t = ' '.join(x for x in out if x)
    t = re.sub(r'\s*(\.\.\.\s*)+', ' ... ', t)
    t = re.sub(r'([(\[])\s*\.\.\.\s*([)\]])', ' ... ', t)     # an emptied parenthesis
    t = re.sub(r'\s*(\.\.\.\s*)+', ' ... ', t)
    t = re.sub(r'\s+([,;:.)\]])', r'\1', t)
    t = re.sub(r'\.\.\.[,;:]', '...', t)
    t = re.sub(r'([,;:—])\s*\.\.\.', ' ...', t)
    t = re.sub(r'\s*(\.\.\.\s*)+', ' ... ', t)
    # a sentence left full of gaps reads as nothing: leave it out whole
    out = []
    for x in chunk.sentences(t):
        gaps = x.count('...')
        rest = len([w for w in x.replace('...', ' ').split() if re.search(r'[A-Za-z]', w)])
        out.append('...' if (gaps >= 3 and rest < 6 * gaps) or (gaps >= 2 and rest < 8) else x)
    t = re.sub(r'\s*(\.\.\.\s*)+', ' ... ', ' '.join(out))
    return t.strip()


def main():
    units = json.load(open(sys.argv[1]))['units']
    res, glog = [], []
    for u in units:
        text = '\n\n'.join(u['paras'])
        lem = find_lemmas(text)
        pieces = []
        if not lem or lem[0][0] > 0:
            head = text[:lem[0][0] if lem else len(text)]
            gloss = ''
            m = re.match(r'([^.,()]{1,40}?),\s*([^.()\[\]]{1,40}?)\.\s', head)    # "Ao'£« bt x.ai ripy, but glory and honour."
            if m and eng_share(m[1]) <= 0.34 and eng_share(m[2]) >= 0.99:
                gloss, head = m[2], head[m.end():]
            pieces.append((gloss, head))
        for k, (b, ge, ce, gloss) in enumerate(lem):
            nxt = lem[k + 1][0] if k + 1 < len(lem) else len(text)
            pieces.append((gloss, text[ce:nxt]))
        lemmas = []
        for gloss, note in pieces:
            note = re.sub(r'^[\s,;:.]+', '', note.strip())
            note = re.sub(r'\s*—\s*$', '', note)
            paras = [scrub(p, glog) for p in note.split('\n\n')]
            paras = [p for p in paras if p.strip(' .') and p.strip() != '...']
            gl = scrub(gloss, glog) if gloss else ''
            gl = gl.strip(' .,;:') if gl.strip(' .') else ''
            if gl == '...':
                gl = ''
            if paras or len(gl.split()) >= 3:
                lemmas.append({'gloss': gl, 'paras': paras})
        res.append({'ch': u['ch'], 'v1': u['v1'], 'v2': u['v2'], 'lemmas': lemmas})
    json.dump({'units': res, 'greek': glog}, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
    print(len(res), 'units', sum(len(u['lemmas']) for u in res), 'lemmas', len(glog), 'greek runs cut')


if __name__ == "__main__":
    main()

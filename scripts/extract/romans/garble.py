"""Find OCR noise that was Greek: a vocabulary of English words from the CCEL transcriptions and the
library's excerpts; a parenthesis whose words are mostly not English is taken for garbled Greek."""
import glob, json, re, os, collections
_V = None
def vocab():
    global _V
    if _V is None:
        words = collections.Counter()
        for f in glob.glob('/home/user/logia/sources/**/*.html', recursive=True) + \
                 glob.glob('/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/hold/sources/**/*.html', recursive=True):
            words.update(re.findall(r'[a-z]+', re.sub(r'<[^>]+>', ' ', open(f, encoding='utf-8').read()).lower()))
        _V = {w for w, n in words.items() if n >= 2}
        global _B
        _B = collections.Counter()
        for w, n in words.items():
            if n >= 2:
                for a, b in zip(w, w[1:]): _B[a + b] += n
    return _V
_B = None
def rare_pair(w):
    vocab()
    return any(_B[a + b] < 50 for a, b in zip(w.lower(), w.lower()[1:]))
def english(tok):
    w = re.sub(r'[^A-Za-z]', '', tok).lower()
    if not w: return False
    if re.search(r'[^A-Za-z.,;:!?\'’‘"“”()\-—]', tok): return False      # @ % & digits inside a word
    return w in vocab()
LATIN = set("ut et in est non ad de ex per cum quod qui quae sed vel aut ab ob sub pro sine nec ne si".split())
def noise(tok):
    """a word that looks like OCR noise: odd characters, a capital inside it, or short and unknown."""
    w = re.sub(r"[’']s$", "", tok.strip('.,;:!?()\'’‘"“”'))
    if not w: return False
    if re.search(r'[^A-Za-z\-]', w): return True          # @ ¢ % & « digits, accented letters
    if re.search(r'[a-z][A-Z]', w): return True            # doyioSein
    if english(w) or w.lower() in LATIN: return False
    return len(w) <= 3 or rare_pair(w)
def greekish(tok):
    """a word that looks like Greek the OCR has garbled (not a reference, not a misread English word)."""
    w = re.sub(r"[’']s$", "", tok.strip('.,;:!?()\'’‘"“”—'))
    if not w or re.search(r'[\d&]', w) or english(w) or w.lower() in LATIN: return False
    if re.search(r'[éèêëáàâäóòôöúùûüíìîïçñ¢©@«»§%+=]', w): return True
    if re.search(r'[a-z][A-Z]', w): return True
    return len(w) >= 4 and rare_pair(w)
def garbled(group):
    toks = [t for t in group.split() if re.search(r'[A-Za-z@¢]', t)]
    if not toks: return False
    if any(english(t) and len(re.sub(r'[^A-Za-z]', '', t)) >= 3 for t in toks): return False
    if re.search(r'\d+\s*:\s*\d|\bp\.\s*\d|&c', group): return False      # a reference
    return any(noise(t) for t in toks)

PAREN = re.compile(r'\s*\(([^()]{1,60})\)')
def strip_greek(p, log=None):
    """p with each garbled-Greek parenthesis taken out and marked ' ... '."""
    def rep(m):
        if garbled(m[1]) and not re.fullmatch(r'[\d\s,.:;—–-]+|[ivxlc]+\.?|vs?\.\s*\d.*|see .*|ch\. .*', m[1].strip(), re.I):
            if log is not None: log.append(m[0].strip())
            return ' ... '
        return m[0]
    out = PAREN.sub(rep, p)
    # a sentence the OCR has filled with Greek noise outside a parenthesis
    import chunk
    kept = []
    for x in chunk.sentences(out):
        toks = [t for t in x.split() if re.search(r'[A-Za-z]', t)]
        bad = [t for t in toks if greekish(t)]
        if len(bad) >= 2 and len(bad) / max(1, len(toks)) >= 0.2:
            if log is not None: log.append('SENT: ' + x)
            kept.append('...')
        else:
            kept.append(x)
    out = ' '.join(kept)
    out = re.sub(r'\s*(\.\.\.\s*)+', ' ... ', out)
    return out.strip()

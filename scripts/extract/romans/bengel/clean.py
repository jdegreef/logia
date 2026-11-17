"""Stage 1: the Romans OCR -> paragraphs, each tagged with chapter, and verse paragraphs found.
Running heads, VOL signatures, junk margin lines and footnotes dropped; line ends joined."""
import html, json, re, sys
sys.path.insert(0, "/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/agent-bengel")
import vocab  # noqa: E402
from greek import inflected  # noqa: E402

SRC = vocab.WT + '/sources/bengel-romans/gnomonofthenewte00benguoft.txt'
W, B = vocab.load()

HEAD = re.compile(r"^\s*\S{0,5}\s*[A-Z]{0,2}[O0]?MAN'?S\s")
SIG = re.compile(r'^\s*(VOL\.\s+III\.?.{0,4}|III\.\s+\S{1,2}|[A-Z])\s*$')
JUNK = {"'  O  cj  1  J  i", "/  '  O", "ft  '", "*•  '  '  cD", "-V.fr", "C;  O  f", "Itl", "O  •<", "O  *"}
FOOT = re.compile(r'^([1-9]|[*†‡])\s+(?!\d\s*\.\s)(?!(Cor|Tim|Thess|Pet|Kings|Sam|Chron|John|Macc|Esd)\b)')
SENT_END = re.compile(r'[.?!:;"”’)\]]\s*$')


def wjoin(a, b):
    """join the last word of one line to the first word of the next?"""
    ma = re.search(r'([A-Za-z]+)(-?)$', a)
    mb = re.match(r'([a-z]+)', b)
    if not ma or not mb:
        return None
    x, y, hy = ma[1].lower(), mb[1].lower(), ma[2]
    if hy:
        return 'nohyphen' if inflected(x + y) or not (inflected(x) and inflected(y)) else 'hyphen'
    if inflected(x + y) and (not inflected(x) or not inflected(y) or W.get(x + y, 0) > 3 * B.get(x + ' ' + y, 0)):
        return 'join'
    return None


def join_lines(lines):
    out = ''
    for ln in lines:
        ln = ' '.join(ln.split())
        if not ln:
            continue
        if not out:
            out = ln
            continue
        j = wjoin(out, ln)
        if j == 'nohyphen':
            out = out[:-1] + ln
        elif j == 'hyphen':
            out = out + ln
        elif j == 'join':
            out = out + ln
        else:
            out = out + ' ' + ln
    return out


ROMAN = re.compile(r'^[ivxlc]+$', re.I)


def drop_markers(p):
    # footnote reference digits stuck to a word: "inscription.1", "volumes,1", "pronoun.1 —"
    def rep(m):
        w = m[1]
        if ROMAN.match(w):
            return m[0]
        return m[1] + m[2]
    return re.sub(r'([A-Za-z]{2,})([.,;:]?)[1-9](?=[\s—)\]]|$)', rep, p)


def pages(text):
    lines = text.split('\n')
    cur, out = [], []
    for ln in lines:
        s = ln.strip()
        if HEAD.match(ln) and len(s) < 45:
            out.append(cur); cur = []; continue
        if SIG.match(ln) or s in JUNK:
            continue
        cur.append(ln)
    out.append(cur)
    return out


def main():
    t = html.unescape(open(SRC, encoding='utf-8').read())
    a = t.find('CHAPTER  I.'); b = t.find('ANNOTATIONS', t.find('XVI.  2G,  27.'))
    t = t[a:b]
    paras, log = [], []
    for pg in pages(t):
        blocks = re.split(r'\n\s*\n', re.sub(r'(?m)^(\s*CHAPT\w+\s+\S+\s*)$', r'\n\1\n', '\n'.join(pg)))
        blocks = [x for x in blocks if x.strip()]
        kept = []
        for i, blk in enumerate(blocks):
            first = blk.strip().split('\n')[0]
            flat = ' '.join(blk.split())
            fend = re.search(r'[—-]\s*(ED|E\s?D|Eo|Eu|E0|E\.?\s?B|Ei>|V\.\s?g|TR)\.?\)?\s*"?\s*$', flat) and \
                flat[:flat.rfind('—') if '—' in flat else len(flat)].count('[') <= flat.count(']')
            if i > 0 and not re.match(r'^\d+\s*[.,]', first) and (FOOT.match(first) or fend):
                log.append(('FOOT', ' | '.join(x.strip()[:200] for x in blocks[i:])))
                break
            if re.fullmatch(r'\W{0,2}[\dJl\]]?\s*See\s+A\s?pp(endix|\.)?[^.]{0,40}\.?\s*', flat):
                log.append(('APP', flat)); continue
            kept.append(blk)
        for i, blk in enumerate(kept):
            p = join_lines(blk.split('\n'))
            if i == 0 and paras and not paras[-1].startswith('CHAPT') \
                    and not re.match(r'^(\d{1,2}[,.\s—–-]|CHAPTER)', p):
                prev = paras.pop()
                p = join_lines([prev, p])
            elif paras and i > 0 and not paras[-1].startswith('CHAPT') and re.match(r'^[a-z]', p) and not SENT_END.search(paras[-1]):
                prev = paras.pop()
                p = join_lines([prev, p])
            paras.append(p)
    paras = [drop_markers(p) for p in paras]
    json.dump({'paras': paras, 'log': log}, open(sys.argv[1], 'w'), ensure_ascii=False, indent=0)
    print(len(paras), 'paragraphs;', len(log), 'footnote blocks')


main()

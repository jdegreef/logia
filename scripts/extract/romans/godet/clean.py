"""Godet OCR -> list of ('para', text) / ('struct', text) items, with heads, page numbers and footnotes dropped."""
import re, html
def upper_share(s):
    L = [c for c in s if c.isalpha()]
    return sum(c.isupper() for c in L) / len(L) if L else 0
def is_head(s):
    if not s: return False
    if re.search(r'(?:^|\s)[VYW][vy][.,]\s*\d|^(?:Vers?|Yers?)[.,]\s*\d|Chap\.\s', s): return False
    if re.search(r'Digitized by|VjOOQ|Google$', s): return True
    if re.fullmatch(r"[\W\dIlSOo]{1,5}", s): return True                       # page number alone
    if len(s) < 45 and re.match(r'^\W{0,2}\s*[CGO]HAP[.,\-\s]', s): return True   # CHAP. L 1, 2. 121
    if len(s) < 45 and re.match(r"^\W{0,2}[\dIlSO]{1,3}\S{0,2}\s+\S", s) and upper_share(s) >= 0.6 and not re.search(r'PASSAGE|SECTION', s):
        return True                                                             # 122 PREFACE.
    if len(s) < 40 and re.search(r'\d{2,3}\s*\.?\s*$', s) and upper_share(s) >= 0.5 and not re.search(r'PASSAGE|SECTION', s): return True
    if len(s) < 40 and re.match(r'^\W{0,2}\s*\S?[A-Za-z]{0,2}[HhBJi][A-Za-z]{0,2}P\.', s) and upper_share(s) >= 0.4: return True
    if len(s) < 25 and re.search(r'G[O0]D[EB][TS]|[BER]OM\.\s*[IL1]|VOL\.\s*I', s): return True   # signature line
    return False
STRUCT = re.compile(r'PASSAGE|SECTION|\bPART\b|TREATISE|^PREFACE|^COMMENTARY|CONCLUSION|PASS\s*AGE')
FN = re.compile(r"^(?:[\^*•>†‡§|+]|'|\d{1,2}|t|J|[\^*]{2})\s+\S")
def lines_of(path):
    t = html.unescape(open(path, encoding='utf-8').read())
    t = re.sub(r'[ \t]+', ' ', t).replace('\r', '')
    return t.split('\n')
def pages(lines):
    """split at running heads; each page a list of lines"""
    out, cur = [], []
    for l in lines:
        s = l.strip()
        if is_head(s):
            if cur: out.append(cur); cur = []
            continue
        cur.append(s)
    if cur: out.append(cur)
    return out
SIG = re.compile(r'(?:^|\s)(?:[A-Z]|Mjj|Mnn|Syr|It|Vulg|Byz|Alex|T\. ?[RBK])[.,:;]?(?=\s|$)')
FNLINE = re.compile(r"^(?:[\^*•>†‡'■]{1,2}|\d)\s+.*\b(?:read|reads|omit|omits|instead|add|adds)\b")
def strip_inline_notes(pg, log):
    out = []; i = 0
    while i < len(pg):
        l = pg[i]
        if l and FNLINE.match(l) and len(SIG.findall(l)) >= 2:
            j = i + 1
            while j < len(pg) and pg[j] and (len(SIG.findall(pg[j])) >= 2 or len(pg[j].split()) < 5) and not re.match(r'^[a-z]', pg[j]):
                j += 1
            log.append('INLINE: ' + ' / '.join(pg[i:j])); i = j; continue
        out.append(l); i += 1
    return out
def strip_footnotes(pg, log):
    pg = strip_inline_notes(pg, log)
    # footnotes sit at the bottom of a page: from a line opening with a marker after a blank line
    # (or within the last 14 lines, with no blank line) to the end of the page
    n = len(pg)
    last = max(i for i, l in enumerate(pg)) if pg else 0
    nonblank = [i for i, l in enumerate(pg) if l]
    if not nonblank: return pg
    lastnb = nonblank[-1]
    for i, l in enumerate(pg):
        if not l or not FN.match(l): continue
        prev_blank = i > 0 and not pg[i - 1]
        near_end = sum(1 for j in nonblank if j >= i) <= 14
        if re.match(r'^\d{1,2}\s+(Cor|Thess|Tim|Pet|John|Kings|Sam|Chron|and|to|or|of|vv?|ver)\b', l): continue
        if (prev_blank and near_end) or (near_end and re.match(r"^(?:[\^*•>†‡']|\d|[\^*'][\^*'])\s+", l) and
                                         re.search(r'\bread|omit|T\. ?[RBK]|Mjj|Mnn|instead|\bIt\b|Syr|\bK\b|\bA\b|\bB\b|\b[A-Z] [A-Z]\b', l)):
            log.append(' / '.join(x for x in pg[i:] if x))
            return pg[:i]
    return pg
END = re.compile(r'[.?!:;"”’)\]*]\s*$')
def items(path, a_mark, b_mark, mark_re, log):
    lines = lines_of(path)
    txt = '\n'.join(lines)
    a = txt.find(a_mark); b = txt.find(b_mark, a) if b_mark else len(txt)
    assert a >= 0 and b > a, (a_mark, b_mark)
    lines = txt[a:b].split('\n')
    pgs = pages(lines)
    LINE_MARK = re.compile(r'^\^?(?:Vers?|Yers?|Vbr|Vv|Yv|Vy|Yy)[.,]\s*\d[^.]{0,12}[.,:]\s+["“\'*^A-Z]')
    out_lines = []
    for pg in pgs:
        pg = strip_footnotes(pg, log)
        pg2 = []
        for l in pg:
            if LINE_MARK.match(l) and pg2 and pg2[-1]: pg2.append('')
            pg2.append(l)
        pg = pg2
        out_lines += pg + ['\x00']          # page break marker
    raw = re.split(r'\n\s*\n', '\n'.join(out_lines))
    res = []
    for p in raw:
        brk = p.strip().endswith('\x00')
        p = re.sub(r'\s*\x00\s*', '\n', p).strip()
        p = re.sub(r'(\w)-\s*\n\s*', r'\1', p)
        p = ' '.join(p.split())
        if not p: continue
        s = p
        if (STRUCT.search(s) and upper_share(s) > 0.6 and len(s) < 80) or re.match(r'^[A-Za-z\-• ]{3,30}PASS\s?AGE\s*[\(Q]', s):
            res.append(['struct', s]); continue
        if len(s) < 60 and upper_share(s) > 0.7:
            res.append(['caps', s]); continue
        if res and res[-1][0] == 'caps' and len(res) > 1 and res[-2][0] == 'para' and not mark_re.match(s) and re.match(r'^[a-z]', s):
            res[-2][1] += ' ' + s; continue
        if re.fullmatch(r'(?:\d\.\s*)?(?:First|Second|Third|Fourth)?\s*\w*\s*:?\s*(?:[VYW][vy][.,]|Chap\.\s*[IVXL]+\.)\s*[\dIlSO]+\s*[-—–]\s*[\dIlSO]+\w?[.,]?', s):
            res.append(['range', s]); continue
        if len(s.split()) <= 8 and not mark_re.match(s) and re.match(r'^[A-Z]', s) and (s.endswith('.') or not re.search(r'[.?!]["”’\']?$', s)):
            res.append(['title', s]); continue
        # join a paragraph broken by a page turn
        if res and res[-1][0] == 'para' and not mark_re.match(s) and (not END.search(res[-1][1]) or re.match(r'^[a-z]', s)):
            res[-1][1] += ' ' + s; continue
        res.append(['para', s])
    # a title-like line followed by a lower-case paragraph was a paragraph's first line;
    # a head-like line between two parts of a paragraph is dropped and the parts joined
    out = []
    for i, it in enumerate(res):
        nxt = res[i + 1] if i + 1 < len(res) else None
        if it[0] == 'title' and nxt and nxt[0] == 'para' and re.match(r'^[a-z]', nxt[1]) and not re.search(r'PASSAGE|[Cc]hap|\d', it[1]):
            nxt[1] = it[1] + ' ' + nxt[1]; continue
        if it[0] == 'para' and out and re.match(r'^[a-z]', it[1]) and not mark_re.match(it[1]):
            j = len(out) - 1
            while j >= 0 and out[j][0] in ('caps', 'title') and not re.search(r'PASSAGE', out[j][1]): j -= 1
            if j >= 0 and j < len(out) - 1 and out[j][0] == 'para':
                out[j][1] += ' ' + it[1]; continue
        out.append(it)
    return out

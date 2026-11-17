import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clean
W = '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/wt-godet/sources/godet-romans/'
MARK = re.compile(r"^\^?(?:Vers?|Yers?|Vbr|Vv|Yv|W|Vy|Yy|Vee)[.,]\s*((?:[\dIlSOo]{1,2}[a-z\^]?\s?[\d]?[a-z]?[\s,.\-—–]*(?:and\s+)?)+?)[.,:]\s*(?=\S)")
VOLS = [('commentaryonstp01cusigoog.txt', 'THE framework of the Epistle', 'END OF VOL. L'),
        ('commentaryonstp00cusigoog.txt', 'FIFTEENTH PASSAGE (VII. 1-6).', 'I ANNOUNCED a chapter')]
def all_items():
    out = []
    for f, a, b in VOLS:
        log = []
        for it in clean.items(W + f, a, b, MARK, log):
            out.append((f, it[0], it[1]))
        out.append((f, 'log', log))
    return out
if __name__ == '__main__':
    for f, k, s in all_items():
        if k == 'log': print('FOOTNOTES', len(s)); continue
        if k == 'para':
            m = MARK.match(s)
            if m: print('MARK', repr(m[1]), s[:50])
        else: print(k.upper(), s[:80])

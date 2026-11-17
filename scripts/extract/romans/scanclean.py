"""Paragraphs of an archive.org OCR text: running heads and page numbers dropped, hyphenated line
ends joined, paragraphs broken by a page turn joined again, footnotes left out."""
import re
END = re.compile(r'[.?!:;"”’)\]]\s*$')
def paragraphs(text, head=re.compile(r'^\s*(?:\d{1,3}\s+)?ROMANS\b[^a-z]{0,30}$|^\s*[\dIl]{1,3}\s*$|^.{0,6}ROMANS\s+\S{1,3}\s*[:;.].{0,16}$'), alone=None, keep=None):
    """alone: a regex for heading lines that stand as paragraphs of their own, never joined."""
    lines = [l for l in text.split('\n') if not head.match(l)]
    raw = re.split(r'\n\s*\n', '\n'.join(lines))
    paras = []
    for p in raw:
        p = re.sub(r'-\s*\n\s*', '', p.strip())        # a word broken at a line end
        p = ' '.join(p.split())
        if not p: continue
        if re.match(r'^[*†‡{+]', p): continue         # a footnote
        if alone and alone.match(p):
            paras.append(p); paras.append(''); continue
        if paras and paras[-1] and not (keep and keep.match(p)) and (not END.search(paras[-1]) or re.match(r'^[a-z]', p)):
            paras[-1] += ' ' + p; continue
        paras.append(p)
    paras = [p for p in paras if p]
    return [re.sub(r'(?<=[\w.,;:’”\'"])\s?[*†‡]+(?=[\s.,;:]|$)', '', p) for p in paras]

"""Paragraphs of a CCEL book-content block: text (notes skipped, as verify_sources does),
the Commentary div id they sit in, their class, and the leading bold/italic text."""
from html.parser import HTMLParser
SKIP = {"Note", "NoteRef", "mnote", "Footnote", "footer_note", "pb", "page"}
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base", "source"}
class P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True)
        s.paras=[]; s.cur=None; s.depth=0; s.stack=[]; s.fmt=[]; s.intable=0
    def handle_starttag(s, tag, attrs):
        if tag in VOID:
            if tag=='br' and s.cur is not None and not s.depth: s.cur['parts'].append(('', ' '))
            return
        a=dict(attrs); cls=set((a.get('class') or '').split())
        if s.depth or cls & SKIP:
            s.depth+=1; return
        if tag=='div': s.stack.append(a.get('id') if 'Commentary' in cls else None)
        if tag=='table': s.intable+=1
        if tag=='p':
            s.cur={'id':a.get('id'),'cls':a.get('class') or '','div':next((x for x in reversed(s.stack) if x),None),'parts':[],'table':s.intable>0}
        if tag in('i','b','em','strong','span','sup','a','h1','h2','h3','h4','h5'): s.fmt.append(tag if tag in ('i','b','em','strong') else (a.get('class') or tag))
        if tag in ('h1','h2','h3','h4','h5'):
            s.cur={'id':a.get('id'),'cls':tag,'div':next((x for x in reversed(s.stack) if x),None),'parts':[],'table':s.intable>0}
    def handle_endtag(s, tag):
        if tag in VOID: return
        if s.depth: s.depth-=1; return
        if tag=='div' and s.stack: s.stack.pop()
        if tag=='table': s.intable-=1
        if tag in('i','b','em','strong','span','sup','a','h1','h2','h3','h4','h5') and s.fmt: s.fmt.pop()
        if tag in ('p','h1','h2','h3','h4','h5') and s.cur is not None:
            s.paras.append(s.cur); s.cur=None
    def handle_data(s, d):
        if s.depth or s.cur is None: return
        s.cur['parts'].append((''.join(f for f in s.fmt if f in('i','b','em')), d))
def paras(path):
    p=P(); p.feed(open(path,encoding='utf-8').read())
    out=[]
    for q in p.paras:
        q['text']=' '.join(''.join(d for _,d in q['parts']).split())
        out.append(q)
    return out

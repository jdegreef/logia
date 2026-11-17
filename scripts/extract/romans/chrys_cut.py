import sys,glob,re,os
sys.path.insert(0,os.path.dirname(__file__)); sys.path.insert(0,'/home/user/logia/scripts')
import ccelparas, chunk, scripture
HORT = re.compile(r"\b(let us|let each|let every one|let him that|let not us)\b", re.I)
def homily(f):
    """(paras, cut) : paras text list; cut = (para index, sentence index) where the exhortation begins."""
    ps=[q['text'] for q in ccelparas.paras(f) if q['text']]
    lv=max(i for i,s in enumerate(ps) if re.match(r'Ver\.',s) or i<4)
    seen=0
    for i in range(lv+1,len(ps)):
        ss=chunk.sentences(ps[i])
        for j,x in enumerate(ss):
            if HORT.search(x.replace('let us do evil','').replace('Let us do evil','')) and seen>=60:
                return ps,(i,j)
            seen+=len(x.split())
    return ps,None
def files():
    return sorted(glob.glob('/home/user/logia/sources/chrysostom-romans/*.html'), key=lambda f: scripture.roman(f.split('.')[-2].upper()))
if __name__=='__main__':
    for f in files():
        ps,cut=homily(f)
        if not cut: print(f[-14:],'NO CUT'); continue
        i,j=cut; ss=chunk.sentences(ps[i])
        kept=sum(len(p.split()) for p in ps[:i])+sum(len(s.split()) for s in ss[:j]); tot=sum(len(p.split()) for p in ps)
        print(f[-14:], f'{kept}/{tot}', '| before:', (ss[j-1][-90:] if j else ps[i-1][-90:]), '|| CUT:', ss[j][:110])

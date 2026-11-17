"""Token-level detection of OCR-garbled Greek in Godet's text."""
import re, sys, os, functools
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/tools')
import garble
HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = set(open(os.path.join(HERE, 'words.txt')).read().split()) | garble.vocab()
# English words (and commentators' names, abbreviations) as the OCR prints them: never taken for Greek
KEEP = set("""hy tiie thai ihe tlie dose bom ths tbe bt ns whidi tenn toe aa bat eta tins aie hf ail uie bj kow tha fiom
lifa ufe heing panl gomp oomp owr amd rer chd thia teal llie tibe mnst sis qf ike mth cmd mare apostie gloiy eveiy veiy
histoiy contraiy passaga eveiything ly ie mj byz mey calv grot thol hofm olsh beng er or chr vat mjj mnn alexs byzs
osterv oltram fritzs fritzsche dietzsch volkmar yolkmar schultz holsten beuss benan bitschl lucht hofinann hilgenfeld
sabatier bonnet morison schott gess oltramare ostervald melanchthon babbins rabbins seq comp ver vv yer yv yy vy vers viz ib
ibid etc cf al gal eph col thess tim tit philem heb pet matt jas apoc introd sect chap chaps vol pp alex alexx greco lat lats
latt itala syr sah cop goth arm aeth vulg bome bom boman bomans ood qod grod gtod oentiles grentiles grentile oreek eome jems
st w t f go de ps p cf ex vs th ch ib vatic firom deaih christy beceived tiiis moie difierent tlus somans yowr hody fiist
ihat haih israd prep eom aposde apostieship jesm beformers oentile babbinical sinait btickert woid bothe yerse bisen tihe
thns hirth fonn epistie teim potoer piel gentilea knoum tliis snch itsell wraih toorld onesdf heen helieveth toas jesua
firat apostla tubingen tiew belieyer beiche woidd faiher wnto bev whieh thej senan lova golossians colosse bufus
recognise develope recognises iil vl xvl vil viil liil lil xxl xll""".split())
SHORT_OK = set("a i o of to in is it or as at be by he we do no so up us my me an on if am ye lo ah oh st w t f go de ps p cf ex vs th ch ib er or hy ia ns bt aa hf bj ly ie ot ol ef pp mm".split())
SHORT_OK -= {'ot', 'ol', 'ef', 'mm'}
GREEKISH = re.compile(r'^(?:ir|tt)[^aeiouyr\s]|^ir[aeo]|(?:ov|ou|ai|oi|ei|eiv|rj|tj|ij|ia9|09|o9|r[jv]|fiev|fiai|iv)$|vp|dv|fii|[^aeiou\s]fi[aeiouv]|^fi[aeiou][^aeiou]?$|^tr[pv]|^sv|^si[kxc]|^ka[prv]|^kcp|^bu?uc|^x[pfve]|pf|jw$|rr$|ij|yy|yr|^sr|^oii|^ipe|^ile|airep|anrep|^aa|^aj|mma|^s?ok|bab$|^(?:tav|tok|beo|seop|sev|tia|aio|kium|bic|apti)$|^svr|^bvi|^bin|^bmp|^enap|^icer|^nofi|^salf|fid|vv|avr|oia$|ota$|epi$|ew$|ii$|qr|^ov|^ro[iu]|^xo|^kp|^ko|^kv|^xa|^neio|^(?:kot|diro|etti|rivi|tcari|ipya)$|^(?:in?r[ie]p|tnrip|ii?r[il]$|roh$|ydp$|avr|oif$|aairep|elye$|sid$|yap|airo|apa|iva|tva|xai|kai|kal|koi|oiv|ovv|ovk|vfi|eir|eif|vtt|ek)')
SLIP = [('U', 'll'), ('U', 'il'), ('U', 'li'), ('ii', 'u'), ('ii', 'n'), ('ii', 'h'), ('im', 'un'), ('Ji', 'h'), ('J', 'h'), ('rn', 'm'),
        ('fi', 'f'), ('fi', 'ffi'), ('ie', 'e'), ('ia', 'a'), ('i', 'l'), ('l', 'i'), ('1', 'l'), ('h', 'b'), ('b', 'h'), ('v', 'u'), ('u', 'n'), ('n', 'u'),
        ('d', 'cl'), ('d', 'el'), ('c', 'e'), ('e', 'c'), ('o', 'e'), ('T', 't'), ('G', 'C'), ('Q', 'G'), ('O', 'G'), ('B', 'R'), ('S', 'R'), ('E', 'R'),
        ('vo', 'w'), ('vn', 'w'), ('L', 'h'), ('U', 'it'), ('U', 'u'), ('Jl', 'h'), ('dl', 'ch'), ('ri', 'n'), ('fi', 'ff'), ('vr', 'w'), ('to', 'w'), ('m', 'in'), ('cl', 'd'), ('ri', 'n'), ('tl', 'd')]
REF = re.compile(r"^(?:[ivxlcz]{1,7}[ILl]?|\d+[>»«*^°]|[\dIlSO]{1,3}[a-c]?|[ivxlcIVXL]{1,6}|[ivxlcz]{1,6}[ILl]|\d+[-—–]\d+[ab]?|\d+(?:st|nd|rd|th|d)|[ivx]+\.?-[ivx]+)$")
def core(tok):
    t = tok
    for _ in range(2):
        t = t.strip('.,;:!?()[]"\'’‘“”—–-').strip('^*•}{|/')
    return t
@functools.lru_cache(None)
def known(w):
    l = w.lower().replace('’', "'")
    l = re.sub(r"'s$", '', l)
    if l in WORDS or l in KEEP: return True
    for suf in ('s', 'es', 'ed', 'd', 'ing', 'ly', 'ness', 'ment', 'er', 'ers', 'ies', 'ied', 'ion', 'ions', 'ity', 'al', 'ally', 'eth', 'th', 'est'):
        if l.endswith(suf) and len(l) > len(suf) + 2:
            b = l[:-len(suf)]
            if b in WORDS or b + 'e' in WORDS or (suf in ('ies', 'ied') and b + 'y' in WORDS): return True
    return False
A = 'abcdefghijklmnopqrstuvwxyz'
@functools.lru_cache(None)
def near(l):
    for i in range(len(l) + 1):
        for c in A:
            if known(l[:i] + c + l[i:]): return True
            if i < len(l) and known(l[:i] + c + l[i + 1:]): return True
        if i < len(l) and known(l[:i] + l[i + 1:]): return True
        if i < len(l) - 1 and known(l[:i] + l[i + 1] + l[i] + l[i + 2:]): return True
    return False
@functools.lru_cache(None)
def slip(w):
    """an English word under a common OCR confusion"""
    for a, b in SLIP:
        i = w.find(a)
        while i >= 0:
            x = w[:i] + b + w[i + len(a):]
            if known(x) and re.fullmatch(r"[A-Za-z']+", x) and (x[1:].islower() or x.isupper() or x[1:] == x[1:].lower()): return True
            i = w.find(a, i + 1)
    return False
def word_greek(w):
    lw = w.lower()
    if lw in KEEP: return False
    if len(w) <= 2: return lw not in SHORT_OK and not w.isupper() and w != 'aU'
    if w in ('Kai', 'Koi', 'Kat', 'Kal', 'Kara', 'Tov', 'Oeov', 'Oeo', 'Oeou', 'Seov', 'Tif', 'Tov'): return True
    if re.search(r'[a-z][A-Z]', w) or (re.match(r'[A-Z]{2}[a-z]', w) and not w.isupper()): return not slip(w)
    if not known(w) and lw not in KEEP and (re.search(r'[bcdfghjklmnpqrstvwxz]{4,}', lw) or re.search(r'[^aeiouy]v$', lw)): return True
    if len(w) <= 2: return w.lower() not in SHORT_OK and not (w.isupper() and len(w) <= 2) and not ('U' in w and slip(w))
    if w in ('Kara', 'Kal', 'Tov', 'Oeov', 'Oeo', 'Oeou', 'Seov'): return True
    if known(w) and not (re.search(r'[a-z][A-Z]', w) and not known(w.lower()) ): return False
    if re.search(r'[a-z][A-Z]', w) or (re.match(r'[A-Z]{2}[a-z]', w) and not w.isupper()): return not slip(w)
    if w[0].isupper() and w[1:].islower():
        if GREEKISH.search(lw): return True
        if len(w) >= 5 and not GREEKISH.search(w.lower()): return False   # a name
        if len(w) >= 4 and not garble.rare_pair(w) and not GREEKISH.search(w.lower()): return False
        return not slip(w)
    if w.isupper(): return len(w) > 4 and not slip(w)
    l = w.lower()
    if GREEKISH.search(l): return True
    if len(l) == 3: return not slip(w)
    if slip(w): return False
    if near(l) and (len(l) >= 7 or not garble.rare_pair(l)): return False
    return True
SAFE_ODD = {'Gk)d', 'Gk>d', 'Gkxl', 'Gh)d', 'Gk)d\'s', 'fix)m', 'fix>m', '&om', '&ct', 'o£', '£ph', 'itsel£', 'God*s', 'believer^s',
            'apostle*8', 'Meyer^s', 'Luther^s', 'fi-om', 'fl>esh', '€rod', '€hd'}
def is_greek(tok):
    w = core(tok)
    if not w or REF.match(w) or w in SAFE_ODD: return False
    if re.fullmatch(r"\d+[a-c]?", w): return False
    if re.fullmatch(r"[A-Za-z]+(?:['’][a-z]{1,2})?(?:-[A-Za-z]+)*", w):
        parts = [p for p in w.split('-') if p]
        if len(parts) > 1:
            if known(w.replace('-', '')): return False
            return any(word_greek(p) for p in parts if not REF.match(p) and p.lower() not in ('co', 're', 'pre', 'non', 'self', 'well', 'ill', 'ex'))
        return word_greek(w)
    if re.fullmatch(r"[\W_]+", w): return bool(re.search(r'[«»#§£¢©@&\\{}<>~€]', w))
    return True

"""Telling the OCR's garbled Greek from English (adapted from tools/garble.py, with a vocabulary from
the worktree's CCEL sources and a rescue for the OCR's usual misreadings of English italics)."""
import collections, re, sys
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/agent-bengel')
import vocab  # noqa: E402

W, _B = vocab.load()
V = {w for w, n in W.items() if n >= 2}
WEB2 = {x.strip().lower() for x in open('/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/agent-bengel/web2.txt')}


def inflected(w):
    if w in V or w in WEB2:
        return True
    for suf, rep in (('ies', 'y'), ('ied', 'y'), ('es', ''), ('s', ''), ('ed', ''), ('ed', 'e'), ('ing', ''),
                     ('ing', 'e'), ('ly', ''), ('er', ''), ('est', ''), ('ment', ''), ('ness', '')):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and (w[:-len(suf)] + rep) in WEB2:
            return True
    return False
CB = collections.Counter()
for w, n in W.items():
    for a, b in zip(w, w[1:]):
        CB[a + b] += n
LATIN = set("""ut et in est non ad de ex per cum quod qui quae sed vel aut ab ob sub pro sine nec ne si
sc viz ver vers engl eng lxx comp cf ed vulg syr orig iren beng gnom app crit append harm ibid
""".split())
# short garbled Greek words the OCR makes again and again (articles, particles)
SHORT = set("""yap xai rov rou tov tou rqv rrjv rrtv rr rb rbv ro ra rcj rw ruv rots rois roTs ovv ovx oux oix
ovd ovds 8e 6e ds dt sv eig tig rig ug uc og iva rr,v rr\\v rfi rri rj r) rjj rij rrj ttj ttjv
tyj ffu xa xara ywp yuo vfj ap fj sx sk sg ej av dia 5/a 3/a d/a ou oy dk oe ds 6s oi ol tv Iv iv ai
el lv py rd ew ara rot tg rr,s rr^ ri^ rr,c rrjs tijs tou rotj ro\\j""".split())
NAMES = set()
CAPS = {'TO', 'T6', 'El', 'IT', 'Ei', 'Ev', 'Eis', 'Oi', 'Ou', 'Tw', 'Ty'}
ONE = set('wuyxqjzrkgmt')
GARBLE = set('''siri adixia abixia xaxia elpsrris dixaioxpiaia faxatoxpisias ddixia puesus tiem ypapri emoreuae Uapidodri
ouopia apaprlas aftapria apapria Adairis eiri rris irlio fyri auri harptia rouror Sisrripridris apifa tudoxia sffri iffri
Xarpsia surripia Tlpovoia aitarri Ppusit irodas Tlddri xaraia
dibio dixatoxpiffia ndio ffari kp apifas theri dvaoyia eire Eire vj fipupari toutois fles maiis pedais vvv fiftli el lv py rd ew 2y
hug raj rap rn pa oj sou ton ric sis om aa apa uri din jn tui vod roi rus tid sia ev ti fa fe vas tai tap aj'''.split())
LATINISH = re.compile(r'(us|um|is|as|ae|ere|are|ire|tur|ntur|que|ibus|orum|arum|tio|tia|tas|tus|ens|ent|ant|unt|ur|ia|io|em|am|es|it|at|ri|or|ix|ex)$')
ROMAN = re.compile(r'^(?=[ivxlc]+$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$')


def core(tok):
    return re.sub(r"[’']s$", "", tok.strip('.,;:!?()[]\'’‘"“”—-'))


def rare_pair(w):
    w = w.lower()
    return any(CB[a + b] < 50 for a, b in zip(w, w[1:]))


VARIANTS = [('ic', 'w'), ('iv', 'w'), ('li', 'h'), ('rn', 'm'), ('ii', 'u'), ('cl', 'd'), ('i', 'l'), ('l', 'i'),
            ('c', 'e'), ('e', 'c'), ('u', 'n'), ('n', 'u'), ('m', 'rn'), ('in', 'm'), ('ni', 'm')]
KEEP = {'bemnning', 'afoses'}          # OCR misreadings of English words (fixed in library/corrections/bengel-romans.json)


def english(w):
    w = w.lower()
    if not w:
        return False
    if inflected(w) or w in LATIN or w in KEEP:
        return True
    if '-' in w and all(inflected(p) for p in w.split('-') if p):
        return True
    if len(w) >= 6:
        for a, b in VARIANTS:
            i = w.find(a)
            while i >= 0:
                if inflected(w[:i] + b + w[i + len(a):]):
                    return True
                i = w.find(a, i + 1)
    if len(w) >= 7 and w.isalpha():
        for i in range(len(w)):
            for ch in 'abcdefghijklmnopqrstuvwxyz':
                if ch != w[i] and inflected(w[:i] + ch + w[i + 1:]):
                    return True
    return False


def greekish(tok):
    """a token that looks like Greek the OCR has garbled."""
    w = core(tok)
    if not w:
        return False
    if re.sub(r'[^A-Za-z]', '', w) in GARBLE:
        return True
    raw = tok.strip('.,;:()[]—-')
    if re.match(r'^[\'"‘’“”]+[A-Za-z]{1,4}$', raw) and not english(raw.strip('\'"‘’“”')) or \
            re.match(r'^[\'"‘’“”]+([A-Z]|[a-z]{1,2})$', raw):
        return True                                    # 'H, "H, 'Ev : a breathing mark
    if re.match(r'^[?!<>$%#@^~]', w) or w in CAPS or w in ONE:
        return True
    if re.search(r'[A-Za-z][;,.!?)(/\\<>$%#@*^~]+[A-Za-z]', w) and not re.fullmatch(r'([a-z]{1,3}\.)+[a-z]{0,3}|([A-Z][a-z]{0,4}\.)+', w):
        return True                                    # p!?a  Ir,ff(iu
    if re.fullmatch(r'\d+(st|nd|rd|th|d|a|b|c|ff?)?\??|[IVXLC]+|[ivxlc]+|[A-Z]|[A-HKLMP]{2,6}|LXX|[A-Z]\.[A-Z]?', w):
        return False                                   # numbers, page refs, MSS sigla (ABCD), roman numerals
    if w in SHORT or w.lower() in SHORT:
        return True
    if re.search(r'[A-Za-z]\d+[A-Za-z]|^\d+[A-Za-z]{2,}', w) and not re.fullmatch(r'\d+(st|nd|rd|th|d)', w):
        return True                                    # 8t6ri
    lt = re.sub(r'[^A-Za-z]', '', w)
    if len(lt) >= 3 and w.lower() not in SHORT and english(lt) and \
            not re.search(r'[^A-Za-z\\_~^}{*#|<>\[\]\d!?\'".,;:’‘“”()\-]', w) and not re.search(r'[a-z][A-Z]', w) \
            and not re.search(r'[A-Za-z][/;,.(][A-Za-z]', w):
        return False                                   # resurrection~\  victor}'  : an English word, OCR'd brackets
    if lt in GARBLE or lt.lower() in GARBLE:
        return True
    if re.match(r'^(Tl|Il)[a-z]', lt) and not english(lt):
        return True                                    # Tlpovoia: the OCR's Pi
    if re.search(r'[éèêëáàâäóòôöúùûüíìîïçñ¢©@«»§%+=/\\|{}<>$*#^~_£€•™]', w):
        return True
    letters = re.sub(r'[^A-Za-z]', '', w)
    if not letters:
        return bool(re.search(r'[^\s.,;:!?—\-\'"“”‘’()\[\]]', w)) and not re.fullmatch(r'[\d&\-–—,.:;]+', w)
    if english(letters) or (len(letters) <= 2 and letters.lower() in V):
        return False
    if re.search(r'[a-z][A-Z]', w):
        return True                                    # doyioSein
    if re.search(r"[A-Za-z][;,.'\"!?)(][A-Za-z]", w):
        return True                                    # Ir,ff(iu
    if re.match(r'^[\'"‘’“”]', w) and len(letters) <= 4:
        return True                                    # 'Ev, 'Ex: a breathing mark
    if letters in NAMES:
        return False
    if len(letters) >= 4 and not rare_pair(letters) and LATINISH.search(letters.lower()):
        return False                                   # a Latin word: proponere, incompositos
    return True


def noise(tok):
    w = core(tok)
    if not w:
        return False
    return greekish(tok) or (len(re.sub(r'[^A-Za-z]', '', w)) <= 3 and not english(re.sub(r'[^A-Za-z]', '', w))
                             and not re.fullmatch(r'\d+|[ivxlcIVXLC]+|[A-Z]', w))


def rare_short(tok):
    """a short word not among the common English ones: next to cut Greek it is Greek too."""
    w = core(tok)
    lt = re.sub(r'[^A-Za-z]', '', w)
    if not lt or len(lt) > 4 or re.fullmatch(r'[ivxlcIVXLC]+\.?|[A-Z]|[A-HKLMP]{2,6}|LXX|ver|vv|ch|cf|comp|etc|ibid|ib|ex|gr|viz|sc|al|Engl|Eng|vers|Vers|Vulg|Syr|App|Gal|Rom|Eph|Col|Heb|Acts|Matt|Mark|Luke|John|Ps|Isa|Is|Jer|Gen|Ex|Lev|Num|Deut|Hos|Joel|Amos|Mic|Hab|Zech|Mal|Dan|Job|Prov|Pet|Tim|Tit|Cor|Jude|Rev|Phil|Kings|Sam|Neh', w):
        return False
    return W.get(lt.lower(), 0) < 300

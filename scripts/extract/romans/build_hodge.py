import sys, re, os, collections
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.environ.get("LOGIA", "/home/user/logia"), "scripts"))
import chunk, scanclean, scripture, garble
ROOT = os.environ.get("LOGIA", "/home/user/logia"); WORK = "hodge-romans"; SRC = "commentaryonepis0000char.txt"
text = open(f'{ROOT}/sources/{WORK}/{SRC}', encoding='utf-8').read()
import html; text = html.unescape(text)
start = text.find('COMMENTARY ON THE ROMANS.')
ALONE = re.compile(r'^(?:CHAP(?:TER)?[.,]?\s+[\dIVXL][^a-z]*|Contents\.|Analysis\.|Commentary\.|Doctrines\.|Remarks\.)$')
body = text[start:]
# a section's name printed on a line with other words ("CHAP. 1: 1—17. Analysis.", "Commentary. 6 (1) What")
body = re.sub(r'(?m)^(Contents|Analysis|Commentary|Doctrines|Remarks)\.[ \t]*', r'\n\n\1.\n\n', body)
body = re.sub(r'(?m)[ \t]+(Contents|Analysis|Commentary|Doctrines|Remarks)\.[ \t]*$', r'\n\n\1.\n\n', body)
MARK = re.compile(r'^(?:\S{1,2}\s)?\((\d+)(?:\s*(?:,|—|–|-|and)\s*(\d+))?\)\s*')
paras = scanclean.paragraphs(body, alone=ALONE, keep=MARK)
units = []; ch = 0; region = False; marks = collections.Counter()
for p in paras:
    m = re.match(r'^CHAPTER ([IVXL]+)\.$', p) or re.match(r'^CHAP(?:TER)?[.,]?\s+(\d+)\s*:', p)
    if m: ch = int(m[1]) if m[1].isdigit() else scripture.roman(m[1]); region = False; continue
    if p in ('Analysis.',): region = True; units.append(None); continue
    if p == 'Commentary.': region = True; units.append(None); continue     # chapter 16 has no Analysis
    p = garble.strip_greek(p)
    if p in ('Doctrines.', 'Remarks.', 'Contents.'): region = False; continue
    if not region or p == 'Commentary.': continue
    mk = MARK.match(p)
    if mk:
        v1 = int(mk[1]); v2 = int(mk[2] or mk[1])
        lemma = p[mk.end():]
        h = re.match(r'(.+?[.?!])(?:\s|$)', lemma); h = h[1] if h else ''
        h = re.sub(r',?\s*&c\.?$', '', h.split(' ... ')[0]).rstrip('.?! ,')
        if len(h.split()) > 12: h = re.split(r'[,;:]', h)[0]
        if len(h.split()) > 12: h = ''
        units.append({'ch': ch, 'v1': v1, 'v2': v2, 'heading': h, 'paras': [p], 'src': SRC})
        marks[ch] += 1
    elif units and units[-1] is not None:
        units[-1]['paras'].append(p)
units = [u for u in units if u]
# the Open Word Bible text has no Romans 16:25-27, so the comment on it has no verse to stand beside

data = chunk.build(WORK, 'ROM', units)
chunk.dump(f'{ROOT}/library/comments/{WORK}/ROM.json', data)
E = data['entries']; L = [len(e['text'].split()) for e in E]
print(len(units), len(E), sum(L), min(L), max(L), sorted(L)[len(L)//2], len({e['start'] for e in E}))
print(sorted(marks.items()))

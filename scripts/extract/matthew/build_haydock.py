"""build_haydock.py: cut Haydock's notes on Matthew from the archive.org transcription into
library/comments/haydock-matthew/MAT.json. Run from the repository root."""
import html, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'romans'))
import chunk
WORK = 'haydock-matthew'
SRC = 'haydock-catholic-bible-comment-haydock-george-leo-3948.txt'
VER = re.compile(r'^Ver\. (\d+)(?:\s*[-–,&]\s*(?:ver\. )?(\d+))*\.')
# Greek the OCR turned into noise, each left out and marked ' ... ' (found by reading every excerpt
# that a search for OCR noise flagged; never retyped)
GREEK = ['Inoouc Xptotos OEOuv VLOG owTNp;', 'Epnuosc,', 'peTtavota,', 'pEeTavoette,', '0 VLOG LOU O ayastnTtoc,',
         'O setpaCwv,', 'apapTlas,', 'Emtotpag@etc Kat ltdov,', 'mpwtompwtov,', 'S€UTEPOMPWTOV,', 'TpttompwTov,',
         '0 mOvnpos,', 'SEUTEPWOELC,', 'MaydaX.av,', 'Mayadav,', '0 yploTtoc, O vtoG;', '0 utoG,',
         'Xtwov is undoubtedly XULEWV,', 'Baptwva', 'TATPWVULLKOV,', 'moet NUEpal OKTW', 'LETALOPPOVOSAL,',
         'Kat nA@ov ets BnOpayn; i.e. EO0pEVOVTO,', 'Twv EX.atwv.', 'etc THV Kouny,', '(ovTOG EoTLv Inoous 0 mpOMNtNS,)',
         'AtdaoKaA0c,', 'EMOPEVETO a0 TOU Lepou,', 'AOWosG LETA AWOV,', '0 u0uEetvas,', 'yOPOUVTES Kal EKyQLLCOVTEG,',
         'MAOXELV,', 'Tov d5€tva;', 'Tov apTov EvYaploTnsEvta,', 'eUAOyNOEV AUTOUG.', '5\\80uEVvov, KA@UEVOV EKYUVOLEVOV.',
         'E€opktGw o€ Kata TOU OEov CwvToOs.', 'pmvnv opKtopov.', '(6nTavTesg avTOV)', 'oppaytCavtes TOV ALEOV,',
         'iis Kal pa mapolé avTtoto Kaéeleto, Kat AaBe youvev.', 'oc nWato youve.', 'WaONTEVELV,']
# the transcription's footnote marks ('[1]', and as the OCR reads them '[1', '(31', "'21", '{21', '\\41', '|!')
FOOTNOTE = re.compile(r"\s(?:\[\d+\]\}?|[\[{]\d(?=\s)|[\[{(]\d1(?=\s)|'\d[1\]]|\\\d1|\|[!)]|\d\|(?=—)|!\d!|(?<=gall\.\s)41(?= The Prot))")
used = set()
def clean(p):
    for g in GREEK:
        if g in p:
            used.add(g); p = p.replace(g, ' ... ')
    p = FOOTNOTE.sub('', p)
    p = re.sub(r'\s*(?:\.\.\.\s*)+', ' ... ', p).replace(' ... .', ' ...').strip()
    return ' '.join(p.split())
def paragraphs(text):
    out = []
    for p in re.split(r'\n\s*\n', text):
        p = re.sub(r'(?<=[a-z])-\s*\n\s*(?=[a-z])', '', p.strip())   # a word broken at a line end
        p = ' '.join(html.unescape(p).split())
        if p: out.append(p)
    return out
def run():
    text = open(f'sources/{WORK}/{SRC}', encoding='utf-8').read()
    a = text.find('\nMATTHEW 1 \n'); b = text.find('HOLY GOSPEL OF JESUS CHRIST, \n\n\nACCORDING TO S. MARK')
    body = text[a:b]
    body = body[:body.rfind('\nMARK')] if '\nMARK' in body else body
    units = []; ch = None; cur = None
    for p in paragraphs(body):
        m = re.match(r'^MATTHEW (\d+)$', p)
        if m:
            ch = int(m[1]); cur = None; continue
        m = VER.match(p)
        if m:
            nums = [int(x) for x in re.findall(r'\d+', m[0])]
            if nums[-1] < nums[0]:   # 'Ver. 26-7.'
                nums[-1] = int(str(nums[0])[:-len(str(nums[-1]))] + str(nums[-1]))
            cur = {'ch': ch, 'v1': nums[0], 'v2': nums[-1], 'heading': '', 'paras': [p], 'src': SRC}
            units.append(cur); continue
        if cur is None:
            print('no verse', ch, p[:70]); continue
        prev = cur['paras'][-1]
        if not re.search(r'[.?!:;"”’)\]]$', prev) or re.match(r'^[a-z]', p):
            cur['paras'][-1] = prev + ' ' + p      # a paragraph the transcription broke mid-sentence
        else:
            cur['paras'].append(p)
    return units
if __name__ == '__main__':
    units = run()
    for u in units:
        u['paras'] = [clean(p) for p in u['paras']]
    assert used == set(GREEK), set(GREEK) - used
    data = chunk.build(WORK, 'MAT', units)
    for e in data['entries']:   # a cut that falls after Haydock's own ' ...' is marked once
        e['text'] = re.sub(r'\.\.\. \.\.\.$', '...', e['text'])
    chunk.dump(f'library/comments/{WORK}/MAT.json', data)
    w = [len(e['text'].split()) for e in data['entries']]
    print(len(units), 'notes', len(data['entries']), 'entries', sum(w), 'words, longest', max(w))

"""Stage 4: lemma units -> library/comments/bengel-romans/ROM.json."""
import collections, json, os, re, sys
sys.path.insert(0, '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/tools')
import chunk  # noqa: E402

WT = '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/wt-bengel'
WORK, BOOK, SRC = 'bengel-romans', 'ROM', 'gnomonofthenewte00benguoft.txt'
MAX, MIN = 350, 80
LAST = {16: 27}
# scan misreadings, fixed at build time (library/corrections/bengel-romans.json); only what the page plainly reads
CORR = [('\\_', '['), ('~\\', ']'), ('bemnning', 'beginning'), ('Afoses', 'Moses'), ('of one mail', 'of one man'),
        ('Mail, who', 'Man, who'), ('of the I icing', 'of the living'), ('Avas not', 'was not'),
        ('arc quite', 'are quite'), ('arc unknown', 'are unknown'), ('Horn. xii.', 'Rom. xii.'), ('Horn. viii.', 'Rom. viii.'),
        ('ice have', 'we have'), ('if ice were', 'if we were'), ('have ice any', 'have we any'), ('as ice owe', 'as we owe'),
        ('as ice behave', 'as we behave'), ('and ice glory', 'and we glory'),
        ('ivith', 'with'), ('ivill', 'will'), ('tlie ', 'the '), ('tliat', 'that'), ('tliou', 'thou'), ('wliich', 'which'),
        ('foreknoicledge', 'foreknowledge'), ('knoivledge', 'knowledge'), ('icasting', 'wasting'), ('icas ', 'was '),
        ('icere', 'were'), ('ichat', 'what'), ('icisdom', 'wisdom'), ('icitli', 'with'), ('icorketh', 'worketh'),
        ('icorks', 'works'), ('icrath', 'wrath'), ('icrite', 'write'), ('ivhere', 'where'), ('ivhich', 'which'),
        ('ivhole', 'whole'), ('ivhorn', 'whom'), ('ivickedness', 'wickedness'), ('ivitness', 'witness'),
        ('ivorking', 'working'), ('ivorks', 'works'), ('ivritten', 'written'), ('poicerless', 'powerless'),
        ('poicer', 'power'), ('qiiestion', 'question'), ('sicear', 'swear'), ('teacli', 'teach'), ('toicards', 'towards'),
        ('trutli', 'truth'), ('worketli', 'worketh'), ('wratli', 'wrath'), ('Gains) a Corinthian', 'Gaius) a Corinthian')]           # bible/owb has no Romans 16:25-27


def wc(s):
    return len(s.split())


def tidy(s):
    s = re.sub(r'^\s*(\.\.\.\s*)+', '', s)
    s = re.sub(r'(\s*\.\.\.)+\s*$', '', s)
    return s.strip()


def lemma_text(lm, inline):
    paras = [p if lm.get('_cut') else tidy(p) for p in lm['paras']]
    lead = bool(lm['paras']) and lm['paras'][0].lstrip().startswith('...') and not lm.get('_cut')
    paras = [p for p in paras if p]
    body = '\n\n'.join(paras)
    if inline and lm['gloss'] and lead and body:
        body = '... ' + body
    if inline and lm['gloss']:
        return lm['gloss'] + ') ' + body if body else lm['gloss'] + ')'
    return body


def pieces_of(lm):
    """a lemma too long for one entry, cut at sentence ends."""
    body = lemma_text(lm, False)
    if wc(body) <= MAX:
        return [dict(lm)]
    out = []
    paras = body.split('\n\n')
    for t in chunk.pack(paras):
        out.append({'gloss': lm['gloss'] if not out else '', 'paras': [t], '_cut': True})
    return out


def entries_of(lemmas):
    """group a unit's lemmas into entries: (heading, text)."""
    flat = []
    for lm in lemmas:
        flat.extend(pieces_of(lm))
    groups, cur = [], []
    for lm in flat:
        size = sum(wc(lemma_text(x, True)) for x in cur)
        if cur and (lm.get('_cut') or cur[-1].get('_cut') or size + wc(lemma_text(lm, True)) > MAX):
            groups.append(cur); cur = []
        cur.append(lm)
    if cur:
        groups.append(cur)
    if len(groups) > 1 and not groups[-1][0].get('_cut') and not groups[-2][-1].get('_cut'):
        a = sum(wc(lemma_text(x, True)) for x in groups[-2]); b = sum(wc(lemma_text(x, True)) for x in groups[-1])
        if b < MIN and a + b <= MAX + 30:
            groups[-2:] = [groups[-2] + groups[-1]]
    out = []
    for g in groups:
        if len(g) == 1:
            out.append((g[0]['gloss'], lemma_text(g[0], False)))
        else:
            out.append(('', ' ... '.join(t for t in (lemma_text(x, True) for x in g) if t)))
    return [(h, t) for h, t in out if t.strip()]


def main():
    units = json.load(open(sys.argv[1]))['units']
    units = [u for u in units if not (u['ch'] in LAST and u['v1'] > LAST[u['ch']])]
    for u in units:
        if u['ch'] in LAST:
            u['v2'] = min(u['v2'], LAST[u['ch']])
    units.sort(key=lambda u: (u['ch'], u['v1']))
    for u in units:
        u['size'] = sum(wc(lemma_text(x, True)) for x in u['lemmas'])
    # a short verse note joins the notes on the verses after it in the same chapter
    merged = []
    for u in units:
        if not u['lemmas']:
            continue
        if merged and merged[-1]['ch'] == u['ch'] and merged[-1]['size'] < MIN and merged[-1]['size'] + u['size'] <= MAX:
            m = merged[-1]
            m['v2'] = max(m['v2'], u['v2']); m['lemmas'] += u['lemmas']; m['size'] += u['size']
            continue
        merged.append(dict(u))
    counts, entries = collections.Counter(), []

    def fixable(h):
        return any(a in h for a, _ in CORR)
    for u in merged:
        key = f"{BOOK}.{u['ch']}.{u['v1']}" + (f"-{u['v2']}" if u['v2'] != u['v1'] else '')
        for h, t in entries_of(u['lemmas']):
            if h and fixable(h):          # a heading is not corrected at build time: put the gloss inline
                t = h + ') ' + t; h = ''
            counts[key] += 1
            entries.append({'id': f'{WORK}.{key}.{counts[key]}', 'start': f"{BOOK}.{u['ch']}.{u['v1']}",
                            'end': f"{BOOK}.{u['ch']}.{u['v2']}", 'heading': h, 'text': t, 'sources': [SRC]})
    path = f'{WT}/library/comments/{WORK}/{BOOK}.json'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(json.dumps({'work': WORK, 'book': BOOK, 'entries': entries},
                                                       ensure_ascii=False, indent=1) + '\n')
    body = '\n'.join(e['text'] for e in entries)
    corr = []
    for a, b in CORR:
        if a in body:
            corr.append({'from': a, 'to': b}); body = body.replace(a, b)
        else:
            print('unused correction', a)
    open(f'{WT}/library/corrections/{WORK}.json', 'w', encoding='utf-8').write(json.dumps({
        'work': WORK,
        'about': 'Scan misreadings in the source text, corrected at build time to match the printed page. Entries keep the '
                 "scan's text; each pair is applied in order to every entry of this work.",
        'corrections': corr}, ensure_ascii=False, indent=1) + '\n')
    per = collections.Counter(int(e['start'].split('.')[1]) for e in entries)
    sizes = [wc(e['text']) for e in entries]
    print(len(entries), 'entries;', dict(sorted(per.items())))
    print('words min/median/max', min(sizes), sorted(sizes)[len(sizes) // 2], max(sizes),
          'under 40:', sum(1 for s in sizes if s < 40), 'over 350:', sum(1 for s in sizes if s > 350))


main()

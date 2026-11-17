"""Turn units (chapter, verse_start, verse_end, heading, [paragraph texts], source) into
Logia entries: every paragraph kept, packed into entries of at most MAX words; a paragraph
longer than MAX is cut at sentence ends, the cut marked with ' ...'."""
import re, json, collections
MAX, MIN = 350, 80
ABBR = set("""st mr mrs dr ver vv viz cf comp etc matt mat rom cor gal eph phil col thess tim tit philem heb
ps psa isa jer ezek dan gen ex exod lev num deut josh judg sam kings chron neh esth prov eccl cant lam hos
mic hab zech mal jas pet jno jn chap ch vol p pp sect sec ibid ib art lib cap i e g n no v vs ii iii iv vi vii
viii ix x xi xii xiii xiv xv xvi lit al seq ff obs hom ep""".split())
END = re.compile(r'(?<=[.!?])([”’"\')\]]*)\s+(?=[“‘"\'(\[]?[A-Z0-9])')
def sentences(p):
    out, last = [], 0
    for m in END.finditer(p):
        before = p[last:m.start()]
        w = re.search(r'(\w+)\.$', before)
        if w and (w[1].lower() in ABBR or len(w[1]) == 1):
            continue
        out.append(p[last:m.end(1)]); last = m.end()
    out.append(p[last:])
    return [s for s in out if s.strip()]
def wc(s): return len(s.split())
def split_long(p, first=MAX):
    """pieces of a paragraph, each at most MAX words (the first at most `first`), cut at sentence ends."""
    if wc(p) <= first: return [p]
    ss = sentences(p); pieces, cur = [], []
    for s in ss:
        cap = first if not pieces else MAX
        if cur and wc(' '.join(cur + [s])) > cap:
            pieces.append(' '.join(cur)); cur = []
        cur.append(s)
    if cur: pieces.append(' '.join(cur))
    # a short tail joins the piece before it if the two still fit under MAX+50
    if len(pieces) > 1 and wc(pieces[-1]) < 60 and wc(pieces[-2]) + wc(pieces[-1]) <= MAX + 80:
        pieces[-2:] = [pieces[-2] + ' ' + pieces[-1]]
    return pieces
def pack(paras):
    """list of entry texts from a unit's paragraphs."""
    blocks = []  # (text, cut_before, cut_after)
    for k, p in enumerate(paras):
        # after a short lead-in (a verse line), the next paragraph's first piece fills the entry
        prev_alone = blocks and not blocks[-1][2] and wc(blocks[-1][0]) < MIN
        ps = split_long(p, MAX - wc(blocks[-1][0]) if prev_alone and wc(p) > MAX - wc(blocks[-1][0]) else MAX)
        for i, x in enumerate(ps):
            blocks.append((x, i > 0, i < len(ps) - 1))
    entries, cur = [], []
    def flush():
        if cur:
            t = '\n\n'.join(x for x, _, _ in cur)
            if cur[0][1]: t = '... ' + t
            if cur[-1][2]: t = t + ' ...'
            entries.append(t); cur.clear()
    for b in blocks:
        size = wc(' '.join(x for x, _, _ in cur))
        lone = len(cur) == 1 and size < MIN      # a verse line alone stays with what follows
        if cur and (cur[-1][2] or b[1] or size + wc(b[0]) > (MAX + 40 if lone else MAX)):
            flush()
        cur.append(b)
    flush()
    # a short piece cut from the paragraph before joins it again when the two fit
    out = []
    for t in entries:
        if out and t.startswith('... ') and out[-1].endswith(' ...') and wc(t) < 60 and wc(out[-1]) + wc(t) <= MAX + 80:
            out[-1] = out[-1][:-4] + ' ' + t[4:]; continue
        out.append(t)
    entries = out
    # a short last entry joins the one before if together they stay within MAX+30
    if len(entries) > 1 and wc(entries[-1]) < MIN and not entries[-1].startswith('...') \
            and not entries[-2].endswith('...') and wc(entries[-2]) + wc(entries[-1]) <= MAX + 30:
        entries[-2:] = [entries[-2] + '\n\n' + entries[-1]]
    return entries
def merge_short(units):
    """a unit under MIN words joins the next unit on the same verse (or the one before), if they fit."""
    out = []
    for u in units:
        u = dict(u)
        if out and out[-1]['_short'] and (out[-1]['ch'], out[-1]['v1'], out[-1]['v2']) == (u['ch'], u['v1'], u['v2']) \
                and wc(' '.join(out[-1]['paras'] + u['paras'])) <= MAX and out[-1]['src'] == u['src']:
            prev = out.pop(); u['paras'] = prev['paras'] + u['paras']; u['heading'] = prev['heading'] or u['heading']
        u['_short'] = wc(' '.join(u['paras'])) < MIN
        out.append(u)
    # a short unit left at the end of a verse joins the unit before it
    res = []
    for u in out:
        if res and u['_short'] and (res[-1]['ch'], res[-1]['v1'], res[-1]['v2']) == (u['ch'], u['v1'], u['v2']) \
                and wc(' '.join(res[-1]['paras'][-1:] + u['paras'])) <= MAX and res[-1]['src'] == u['src'] \
                and len(pack(res[-1]['paras'] + u['paras'])) == len(pack(res[-1]['paras'])):
            res[-1] = dict(res[-1], paras=res[-1]['paras'] + u['paras']); continue
        res.append(u)
    return res
def build(work, book, units, extra=None):
    units = merge_short([u for u in units if any(p.strip() for p in u['paras'])])
    units.sort(key=lambda u: (u['ch'], u['v1']))  # stable
    counts = collections.Counter(); entries = []
    for u in units:
        start = f"{book}.{u['ch']}.{u['v1']}"; end = f"{book}.{u['ch']}.{u['v2']}"
        key = f"{book}.{u['ch']}.{u['v1']}" + (f"-{u['v2']}" if u['v2'] != u['v1'] else '')
        for i, t in enumerate(pack(u['paras'])):
            counts[key] += 1
            e = {"id": f"{work}.{key}.{counts[key]}", "start": start, "end": end,
                 "heading": u['heading'] if i == 0 else "", "text": t, "sources": [u['src']]}
            entries.append(e)
    return {"work": work, "book": book, "entries": entries}
def dump(path, data):
    import os; os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=1))

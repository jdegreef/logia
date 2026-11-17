"""English vocabulary (words and bigrams) from the CCEL transcriptions saved in the worktree's sources."""
import collections, glob, html, json, os, re
WT = '/tmp/claude-0/-home-user-logia/f6088232-4482-54bc-9abc-1d9c529c2ab1/scratchpad/wt-bengel'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vocab_cache.json')


def load():
    if os.path.exists(CACHE):
        d = json.load(open(CACHE))
        return collections.Counter(d['w']), collections.Counter(d['b'])
    words, bi = collections.Counter(), collections.Counter()
    for f in glob.glob(WT + '/sources/**/*.html', recursive=True):
        t = html.unescape(re.sub(r'<[^>]+>', ' ', open(f, encoding='utf-8').read()))
        toks = re.findall(r"[A-Za-z]+", t)
        low = [x.lower() for x in toks]
        words.update(low)
        bi.update(a + ' ' + b for a, b in zip(low, low[1:]))
    ocr = collections.Counter()
    for f in glob.glob(WT + '/sources/ryle/*.txt') + glob.glob(WT + '/sources/catena/*.txt'):
        ocr.update(x.lower() for x in re.findall(r"(?<![A-Za-z])[a-z]+(?![A-Za-z])", html.unescape(open(f, encoding='utf-8').read())))
    words = collections.Counter({w: n for w, n in words.items() if n >= 2})
    for w, n in ocr.items():
        if n >= 3:
            words[w] += n
    bi = collections.Counter({w: n for w, n in bi.items() if n >= 2})
    json.dump({'w': words, 'b': bi}, open(CACHE, 'w'))
    return words, bi

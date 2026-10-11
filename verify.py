"""Check that quoted lines in an answer really appear in the retrieved rule text.

Exact match tolerates only things that are in the data but not in the rule itself:
  - running page headers ("Rule 56 M.P. Bhumi Vikas Rules, 2012 78")
  - footnote markers ("1[" and a lone digit on a line)
  - "..." / "[...]" used by Claude to join two parts of one rule
If that fails, a second "table" check accepts a quote whose words all appear IN ORDER close together
in the rule text. This covers flattened tables, where another column's text sits between the words.
Paraphrases are not accepted.
"""
import re

_HDR = re.compile(r"(?:Rule\s+\S+\s+)?M\.?\s?P\.?\s+Bhumi\s+Vikas\s+Rules,?\s+2012\s+\d+", re.I)
_FOOT = re.compile(r"(?<![\w.])\d{1,2}\[")
_LONE = re.compile(r"(?m)^\s*\d{1,2}\s*$")
_ELL = re.compile(r"\s*(?:\[\s*\.\.\.\s*\]|\.\.\.|\u2026)\s*")
_CURLY = re.compile(r"\u201c([^\u201d]*)\u201d")
_STRAIGHT = re.compile(r'"([^"]*)"')
_WORD = re.compile(r"[0-9a-z\u0900-\u097f]+")


def clean(text):
    t = _HDR.sub(" ", text)
    t = _FOOT.sub(" ", t)
    return _LONE.sub(" ", t)


def norm(s):
    return re.sub(r"[^0-9a-z\u0900-\u097f]+", "", s.lower())


def corpus_for(rules_by_num, nums):
    out = {}
    for n in nums:
        if n in rules_by_num:
            t = clean(rules_by_num[n]["text"])
            out[n] = (norm(t), _WORD.findall(t.lower()))
    return out


def find_quotes(answer):
    """Pair quote marks first, then drop short ones, so a short quote cannot shift the pairing."""
    found = []
    rest = _CURLY.sub(lambda m: (found.append(m.group(1)) or " "), answer)
    found += [m.group(1) for m in _STRAIGHT.finditer(rest)]
    return [q for q in found if len(q.strip()) >= 15]


def _in_order(qw, tw):
    if len(qw) < 5:
        return False
    limit = len(qw) * 2 + 6
    for i, w in enumerate(tw):
        if w != qw[0]:
            continue
        end = min(len(tw), i + limit)
        j, ok = i, True
        for q in qw[1:]:
            j += 1
            while j < end and tw[j] != q:
                j += 1
            if j >= end:
                ok = False
                break
        if ok:
            return True
    return False


def match_quote_ex(quote, corpus):
    """Return (rule number, "exact" or "table"), or (None, None)."""
    parts = [norm(p) for p in _ELL.split(quote)]
    parts = [p for p in parts if len(p) >= 8]
    if not parts:
        return None, None
    for n, (text, _) in corpus.items():
        if all(p in text for p in parts):
            return n, "exact"
    segs = [_WORD.findall(p.lower()) for p in _ELL.split(quote)]
    segs = [s for s in segs if len(s) >= 5]
    for n, (_, words) in corpus.items():
        if segs and all(_in_order(s, words) for s in segs):
            return n, "table"
    return None, None


def match_quote(quote, corpus):
    return match_quote_ex(quote, corpus)[0]

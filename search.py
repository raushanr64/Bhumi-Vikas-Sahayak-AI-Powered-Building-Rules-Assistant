"""Load the Bhumi Vikas rules and search them with BM25.

Usage:
    python search.py "front setback for 200 sq m plot"
    python search.py --fields        (shows the field names found in the data)
"""
import json
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

DATA_FILE = Path(__file__).parent / "data" / "bhumi_vikas_rules.jsonl"

# Possible field names. The first one present in a record is used.
NUMBER_KEYS = ["rule_number", "rule_no", "rule_num", "number", "rule"]
TITLE_KEYS = ["title", "rule_title", "heading"]
TEXT_KEYS = ["text", "full_text", "rule_text", "content"]
PAGE_START_KEYS = ["page_start", "start_page", "pdf_page_start"]
PAGE_END_KEYS = ["page_end", "end_page", "pdf_page_end"]


def _pick(record, keys):
    for k in keys:
        if k in record and record[k] not in (None, ""):
            return record[k]
    return ""


def load_rules(path=DATA_FILE):
    rules = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rules.append(
                {
                    "number": str(_pick(r, NUMBER_KEYS)),
                    "title": str(_pick(r, TITLE_KEYS)),
                    "text": str(_pick(r, TEXT_KEYS)),
                    "page_start": _pick(r, PAGE_START_KEYS),
                    "page_end": _pick(r, PAGE_END_KEYS),
                    "raw": r,
                }
            )
    return rules


STOPWORDS = set("""
a an the and or of to in on at for from by with without is are was were be been being it its this that
these those my me i we you your our do does did done can could should would will shall may might must
how what when where which who whom whose why if then than so as not no any all each per into upon
about over under after before between there their they them he she his her has have had also such
""".split())

_SUFFIXES = ("ations", "ation", "ities", "ity", "ings", "ing", "ed", "es", "al", "ly", "s")


def _stem(w):
    """Very light stemmer so valid/validity and renew/renewed/renewal match."""
    if w.isdigit():
        return w
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokenize(s):
    words = re.findall(r"[a-z0-9]+", s.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]


# Clerk words -> rulebook words. Added to the query before searching.
SYNONYMS = {
    r"\bdeadline\b|\bnot replied\b|\bno reply\b|\bno response\b|\bdelay": "limitation period refusal intimate deemed sanctioned",
    r"\bfee\b": "fees",
    r"\bdisagree|\bconflict|\bcontrary\b": "different contrary development plan precedence",
    r"\bchange (my|the) plan\b|\bchange plan\b": "deviation sanctioned plan",
    r"\bdocuments?\b": "information accompanying application",
    r"\bwho (can|is allowed to) sign": "preparation signing plans architect engineer licensed",
    r"\blifts?\b|\belevator": "provision of lifts",
    r"\bsetback\b|\bgap\b|\bopen space\b": "open spaces front rear side marginal",
}


def expand_query(query):
    q = query.lower()
    extra = [words for pat, words in SYNONYMS.items() if re.search(pat, q)]
    return query + " " + " ".join(extra) if extra else query


def rule_refs(query):
    """Rule numbers a question names, e.g. "Rule 2(5)(c)" -> {"2"}, "rule 25(A)" -> {"25", "25(a)", ...}.

    Sub-clauses like (5)(c) are dropped because the data holds one record per rule.
    (The old code looked for the text "2(" and so never found Rule 2.)
    """
    refs = set()
    pat = r"(?:\brule|नियम)\s+(\d+)(?:\s*-\s*([a-z])(?![a-z])|\(([a-z])\))?"
    for m in re.finditer(pat, query.lower()):
        base, dash, paren = m.group(1), m.group(2), m.group(3)
        refs.add(base)
        letter = dash or paren
        if letter:
            refs |= {f"{base}-{letter}", f"{base}({letter})", f"{base}{letter}"}
    return refs


class RuleSearch:
    def __init__(self, rules):
        self.rules = rules
        # Title is repeated so title words count more than body words.
        docs = [tokenize((r["title"] + " ") * 3 + r["text"]) for r in rules]
        self.bm25 = BM25Okapi(docs)

    def search(self, query, k=5):
        scores = list(self.bm25.get_scores(tokenize(expand_query(query))))
        # If the user names a rule ("rule 12", "Rule 2(5)(c)", "नियम 56"), push that rule up.
        wanted = rule_refs(query)
        if wanted:
            for i, r in enumerate(self.rules):
                if r["number"].lower().replace(" ", "") in wanted:
                    scores[i] += 1000
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.rules[i], scores[i]) for i in order]


if __name__ == "__main__":
    rules = load_rules()
    if len(sys.argv) > 1 and sys.argv[1] == "--fields":
        print("Rules loaded:", len(rules))
        print("Field names in data:", list(rules[0]["raw"].keys()))
        print("First rule number/title/pages:", rules[0]["number"], "|", rules[0]["title"],
              "|", rules[0]["page_start"], "-", rules[0]["page_end"])
        print("Text length of first rule:", len(rules[0]["text"]))
        sys.exit(0)

    query = " ".join(sys.argv[1:]) or "front setback for 200 sq m plot"
    engine = RuleSearch(rules)
    for rule, score in engine.search(query):
        print(f"Rule {rule['number']} | {rule['title']} | pages {rule['page_start']}-{rule['page_end']} | score {score:.2f}")
        print("   ", rule["text"][:150].replace("\n", " "), "...")

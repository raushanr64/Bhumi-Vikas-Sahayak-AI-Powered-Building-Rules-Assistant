"""Answer a clerk's question using only the retrieved rules.

Usage:
    set ANTHROPIC_API_KEY=your_key        (Windows)
    python answer.py "My house faces a 10 m street and is 9 m tall. Front open space?"
"""
import json
import os
import re
import sys

import anthropic
try:
    import httpx2 as httpx  # this environment's Anthropic SDK needs httpx2
except ImportError:
    import httpx

from pathlib import Path

from search import RuleSearch, load_rules


def _load_dotenv():
    """Read ANTHROPIC_API_KEY from a local .env file if there is one (.env is in .gitignore)."""
    path = Path(__file__).parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip("\"'")  # .env wins over any old key in the terminal


_load_dotenv()

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
RULES_VERSION = "MP Bhumi Vikas Rules 2012, consolidated up to 6 March 2025"
_AMEND_FILE = Path(__file__).parent / "amendments.json"
AMENDMENTS = json.loads(_AMEND_FILE.read_text(encoding="utf-8")) if _AMEND_FILE.exists() else []

SYSTEM_PROMPT = f"""You help a building-permission clerk at Bhopal Municipal Corporation.
You are given excerpts from the {RULES_VERSION}.

Strict rules:
1. Answer ONLY from the excerpts. Never use outside knowledge. Never invent a rule, number or fee.
2. Start with a short direct answer (2-3 sentences), then list at most 3 sources. The whole reply
   should stay under about 200 words: the clerk has one minute.
3. For every claim give the rule number, e.g. "Rule 17", and quote the exact text it came from
   inside quotation marks. Quote only the sentence or table row that carries the answer, not the
   whole rule. Copy numbers from tables exactly. Do not do your own arithmetic;
   if a calculation is needed, show the inputs and say it must be calculated.
4. Tables in the excerpts are flattened. If a table value is unclear or ambiguous, say so and
   tell the clerk to check the PDF page.
5. If the excerpts do not answer the question, reply exactly with the single word NOT_FOUND
   and nothing else.
6. Reply in the same language as the question (English or Hindi). Rule numbers and quotes stay in English.
7. You point to the rule; the clerk decides. Do not give legal advice.
8. For a number taken from a table, name the condition you matched (for example the street-width
   band or height band) and the rule. If the flattened table could be read in more than one way,
   say that and do not pick one.
9. If the question asks for a list (documents, conditions, requirements), give only the items that are
   in the excerpts, and say if the excerpts refer to another rule, form or appendix that is not shown.
   Never present a partial list as complete."""


HI_NOTE = (
    "\n\nWrite the answer in simple Hindi (Devanagari script). Keep rule numbers and quoted rule text "
    "in English exactly as in the excerpts. If the excerpts do not answer, reply exactly NOT_FOUND."
)


def has_devanagari(s):
    return bool(re.search(r"[ऀ-ॿ]", s))


# Hindi written in English letters (Hinglish), common at a counter.
_HINGLISH = re.compile(
    r"\b(kya|kaise|kaisa|kitna|kitni|kitne|kab|kahan|kyun|liye|karna|karni|karen|kare|chahiye|"
    r"nahi|nahin|mera|meri|mere|hamara|hai|hain|hota|hoga|hogi|lagta|lagega|lagegi|banana|banane|"
    r"jagah|sadak|zameen|jamin|makaan|ghar|dukan|naksha|nakshe|manzil|chhodni|chhodna)\b",
    re.I,
)


def is_indic(s):
    return has_devanagari(s) or bool(_HINGLISH.search(s))


_ANTHROPIC_CLIENT = None


def client():
    """Return a reusable Anthropic client using httpx."""
    global _ANTHROPIC_CLIENT

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY first (environment variable, local .env file, or app sidebar)."
        )

    if _ANTHROPIC_CLIENT is None:
        http_client = httpx.Client(
            headers={"Accept-Encoding": "identity"},
            timeout=30.0,
        )
        _ANTHROPIC_CLIENT = anthropic.Anthropic(
            http_client=http_client,
            max_retries=0,
        )

    return _ANTHROPIC_CLIENT


def reply_text(msg):
    """Join only the text blocks; the model may put a thinking block first."""
    return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text").strip()


def to_english_query(c, question):
    """BM25 works on English text, so turn a Hindi question into an English search query."""
    if not is_indic(question):
        return question
    msg = c.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": "Translate this building-permission question into a short English search "
                       "query. Output only the query.\n\n" + question,
        }],
    )
    return reply_text(msg)


def format_excerpts(hits):
    parts = []
    for rule, _ in hits:
        parts.append(
            f"[Rule {rule['number']} | {rule['title']} | PDF pages {rule['page_start']}-{rule['page_end']}]\n"
            f"{rule['text']}"
        )
    return "\n\n-----\n\n".join(parts)


def needs_split(q):
    """Only call Claude to split/translate when the question looks multi-part or is Hindi."""
    return is_indic(q) or q.count("?") > 1 or bool(re.search(r"\band\b|,|;", q.lower()))


def plan_queries(c, question):
    """Return 1-3 short English search queries, one per thing the clerk is asking."""
    if not needs_split(question):
        return [question]
    try:
        msg = c.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": "Turn this building-permission question into 1 to 3 short English search "
                           "queries, one for each distinct thing asked (for example setback, floors, "
                           "fee). Translate if it is Hindi. Output ONLY a JSON list of strings.\n\n"
                           + question,
            }],
        )
        m = re.search(r"\[.*\]", reply_text(msg), re.S)
        qs = [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()][:3]
        if qs:
            return qs
    except Exception:
        pass
    return [to_english_query(c, question)]


def retrieve(engine, queries, k):
    """Search each sub-query, then merge round-robin so every part of the question gets rules."""
    each = k if len(queries) == 1 else 4
    lists = [engine.search(q, k=each) for q in queries]
    if len(queries) > 1:
        lists.append(engine.search(" ".join(queries), k=each))
    merged, seen = [], set()
    for rank in range(each):
        for lst in lists:
            if rank < len(lst) and lst[rank][0]["number"] not in seen:
                seen.add(lst[rank][0]["number"])
                merged.append(lst[rank])
    return merged[: k + 2]


def matching_amendments(text):
    """Amendments whose hint words or patterns appear in the question (or its English search query)."""
    t = re.sub(r"\s+", " ", text.lower())
    return [a for a in AMENDMENTS
            if any(h.lower() in t for h in a.get("hints", []))
            or any(re.search(p, t) for p in a.get("patterns", []))]


# ---- notes shown next to an answer (plain rules, no AI) ----
_LIST_Q = re.compile(r"\b(documents?|checklist|list of|requirements?|conditions|enclose[sd]?|attach(ed|ment)?s?)\b"
                     r"|दस्तावेज|कागज|सूची|dastavej|kagaz", re.I)
_REFS = re.compile(r"\b(Appendix\s+[A-Z0-9]{1,3}|Form\s+[A-Z0-9][A-Z0-9\-]{0,3}|Schedule\s+[A-Z0-9]{1,3})\b")


def cited_rules(text, hits):
    """Retrieved rules that the answer actually names ("Rule 56"), with their PDF pages."""
    out = []
    for rule, _ in hits:
        if re.search(rf"\bRule\s+{re.escape(rule['number'])}(?![\w])", text):
            out.append((rule["number"], rule["title"], rule["page_start"], rule["page_end"]))
    return out


def answer_notes(question, text, hits, cited):
    """Warnings for the clerk. They never add rule content; they say where the answer may be weak."""
    by_num = {r["number"]: r for r, _ in hits}
    pages = ", ".join(f"Rule {n}: PDF p.{a}-{b}" for n, _, a, b in cited) or "see the retrieved rules"
    notes = []
    cited_text = " ".join(by_num[n]["text"] for n, *_ in cited if n in by_num)
    # A table is flagged if the rule says "table", or if a decimal in the answer (2.5, 3.6) sits in the rule
    # text: flattened table rows often have no "table" word near them.
    decimals = set(re.findall(r"\d+\.\d+", text))
    table_like = bool(re.search(r"\btable\b", cited_text, re.I)) or any(d in cited_text for d in decimals)
    if table_like and re.search(r"\d", text):
        notes.append("TABLE: this answer uses numbers from a rule that contains tables. The tables are flattened "
                     "text, so a number can sit under the wrong column. Check the number on the PDF page "
                     f"before you tell the citizen ({pages}).")
    if _LIST_Q.search(question):
        extra = sorted(set(_REFS.findall(cited_text)))[:6]
        extra = [e if isinstance(e, str) else e[0] for e in extra]
        more = (" The cited rule text also mentions: " + ", ".join(extra) + ". Those are not shown in this answer.") if extra else ""
        notes.append("LIST: this lists only what the retrieved rules say. It may not be the complete list "
                     f"(other rules, forms or appendices may add items).{more} Check the full rule ({pages}).")
    return notes


def answer(question, engine, k=8, c=None, lang=None):
    c = c or client()
    queries = plan_queries(c, question)
    query = " | ".join(queries)
    hits = retrieve(engine, queries, k)
    amendments = matching_amendments(question + " " + query)
    have = {r["number"] for r, _ in hits}
    for a in amendments:
        # e.g. Rule 2(5)(c) lives inside Rule 2, permission is in Rule 12: show both on this topic.
        for num in a.get("force_rules", []):
            if num not in have:
                rule = next((r for r in engine.rules if r["number"] == num), None)
                if rule:
                    hits.append((rule, 0.0))
                    have.add(num)
    msg = c.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Excerpts:\n\n{format_excerpts(hits)}\n\nQuestion: {question}" + HI_NOTE * (lang == "hi"),
        }],
    )
    text = reply_text(msg)
    not_found = text.upper().startswith("NOT_FOUND")
    warning = ""
    if amendments:
        warning = ("Changes after 6 March 2025 may apply (NOT in the rule text above): "
                   + "; ".join(f"Rule {a['rule']}, {a['date']} ({a['status']})" for a in amendments)
                   + ". Check the latest notification.")
    cited = [] if not_found else cited_rules(text, hits)
    notes = [] if not_found else answer_notes(question + " " + query, text, hits, cited)
    not_found_note = ""
    if not_found and amendments:
        not_found_note = ("The March 2025 rule text that was searched does not answer this. A later change "
                          "may apply: see the amendment box. It is a secondary summary, not the notification.")
    return {
        "question": question,
        "search_query": query,
        "answer": "Not found in the rulebook." if not_found else text,
        "cited": cited,
        "notes": notes,
        "not_found_note": not_found_note,
        "not_found": not_found,
        "sources": [(r["number"], r["title"], r["page_start"], r["page_end"]) for r, _ in hits],
        "version": RULES_VERSION,
        "amendments": amendments,
        "amendment_warning": warning,
    }


def general_note(question, c=None, lang=None):
    """Opt-in pointer for questions the rulebook does not cover. Never cites rules, fees or numbers."""
    c = c or client()
    msg = c.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=(
            "A building-permission clerk in Bhopal asked something the rulebook (MP Bhumi Vikas Rules, 2012) "
            "does not cover. Give a SHORT general pointer, under 80 words, in the language of the question. "
            "Start with: 'Not from the rulebook.' Say which kind of office, department or document could help. "
            "Do NOT cite rule numbers. Do NOT state any fee, rate, deadline, area, distance or legal requirement. "
            "If you are not sure, say so and tell the clerk to check with a senior or the department."
        ),
        messages=[{"role": "user", "content": question + (
            "\n\n(Reply in Hindi, Devanagari script. Start with: 'नियम-पुस्तिका से नहीं।')" if lang == "hi" else "")}],
    )
    return reply_text(msg)


def print_result(res):
    print("\nQ:", res["question"])
    print("Search query used:", res["search_query"])
    print("\n" + res["answer"])
    if res.get("cited"):
        print("\nCited:", ", ".join(f"Rule {n} (PDF p.{a}-{b})" for n, _, a, b in res["cited"]))
    for n in res.get("notes", []):
        print("NOTE:", n)
    if res.get("not_found_note"):
        print("NOTE:", res["not_found_note"])
    print("\nRetrieved rules:", ", ".join(f"Rule {n} (p.{a}-{b})" for n, _, a, b in res["sources"]))
    print("Version:", res["version"])
    if res["amendment_warning"]:
        print(res["amendment_warning"])


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    if not q:
        sys.exit('Usage: python answer.py "your question"')
    print_result(answer(q, RuleSearch(load_rules())))

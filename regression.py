"""Regression tests: the 10 manual test questions, plus offline checks of the new code.

    python regression.py            offline checks only (no API key, no internet)
    python regression.py --live     also runs the 10 questions through Claude (needs ANTHROPIC_API_KEY)

What this tests: behaviour (right rule found and named, NOT_FOUND when the rules are silent,
amendment box shown, warnings shown, Hindi answer in Hindi).
What this does NOT test: whether an answer is legally correct. Every number must still be checked
against the PDF by a person. Only the front-setback values below were read from the Rule 56(1)(a)
table by the team (see README); the other cases do not assert any number.
Results are written to regression_results.md.
"""
import re
import sys
import time

import answer as A
from search import RuleSearch, load_rules, rule_refs

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []   # (group, name, status, detail)


def record(group, name, ok, detail=""):
    status = PASS if ok else FAIL
    results.append((group, name, status, detail))
    print(f"[{status}] {group}: {name} {detail}")


def skip(group, name, why):
    results.append((group, name, SKIP, why))
    print(f"[{SKIP}] {group}: {name} ({why})")


# ---------------------------------------------------------------- offline checks
def offline():
    # 1. Amendment matching (this is what failed in manual test 9).
    should_match = [
        "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
        "What does Rule 2(5)(c) say?",
        "what does rule 2 (5) (c) say about plots",
        "Can I build on a 500 sq m plot without separate permission?",
        "500sqm plot permission",
        "500 वर्ग मीटर तक के प्लॉट के लिए विकास अनुज्ञा चाहिए क्या?",
    ]
    for q in should_match:
        ids = [a["id"] for a in A.matching_amendments(q)]
        record("amendment-match", q[:60], "2-5-c" in ids, f"-> {ids}")
    should_not_match = [
        "I want a farm house on agricultural land. What is the minimum plot size and the maximum FAR?",
        "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?",
        "What is the minimum rear open space for a 150 sq m residential plot?",
        "How do I pay my property tax online?",
    ]
    for q in should_not_match:
        ids = [a["id"] for a in A.matching_amendments(q)]
        record("amendment-no-false-alarm", q[:60], "2-5-c" not in ids, f"-> {ids}")
    ids = [a["id"] for a in A.matching_amendments("Extra FAR for a green building with GRIHA rating?")]
    record("amendment-match", "green building", "5-6" in ids, f"-> {ids}")

    # 2. Rule names inside a question.
    record("rule-ref", "Rule 2(5)(c) -> {2}", rule_refs("What does Rule 2(5)(c) say?") == {"2"})
    record("rule-ref", "rule 56", rule_refs("explain rule 56") == {"56"})
    record("rule-ref", "Rule 25(A)", {"25", "25(a)"} <= rule_refs("see Rule 25(A)"))
    record("rule-ref", "rules 2012 is not a rule", rule_refs("MP Bhumi Vikas Rules 2012") == set())
    record("rule-ref", "Hindi नियम 12", rule_refs("नियम 12 क्या कहता है") == {"12"})

    # 3. Cited rules, table note, list note (synthetic rules, not real rule text).
    r56 = {"number": "56", "title": "Open spaces", "page_start": 78, "page_end": 79,
           "text": "Table 3 front open space 3.0 3.6 4.5 6.0"}
    r16 = {"number": "16", "title": "Documents", "page_start": 30, "page_end": 30,
           "text": "The application shall be accompanied by the documents listed in Appendix B and Form 2."}
    r21 = {"number": "21", "title": "Fees", "page_start": 40, "page_end": 40, "text": "Fee per square meter."}
    hits = [(r56, 1.0), (r16, 0.9), (r21, 0.8)]
    ans = 'Front open space is 3.6 m. Rule 56: "Table 3 front open space 3.6".'
    cited = A.cited_rules(ans, hits)
    record("cited", "only Rule 56 is cited", [c[0] for c in cited] == ["56"], f"-> {cited}")
    notes = A.answer_notes("front open space", ans, hits, cited)
    record("notes", "table note shown for a table rule", any(n.startswith("TABLE") for n in notes))
    r52 = {"number": "52", "title": "Electric lines", "page_start": 60, "page_end": 60,
           "text": "Low and Medium voltage lines and service lines 2.5 1.2"}   # synthetic: no word "table"
    ans52 = "Clearance is 2.5 m vertical and 1.2 m horizontal. Rule 52."
    n52 = A.answer_notes("balcony electric line clearance", ans52, [(r52, 1.0)], A.cited_rules(ans52, [(r52, 1.0)]))
    record("notes", "table note shown when the rule has numbers but no word 'table'", any(n.startswith("TABLE") for n in n52))
    ans2 = "Documents are in Rule 16."
    cited2 = A.cited_rules(ans2, hits)
    notes2 = A.answer_notes("What documents go with the application?", ans2, hits, cited2)
    record("notes", "list note shown for a documents question", any(n.startswith("LIST") for n in notes2))
    record("notes", "list note names Appendix B / Form 2",
           any("Appendix B" in n and "Form 2" in n for n in notes2), f"-> {notes2}")
    record("cited", "Rule 2 does not match Rule 21",
           A.cited_rules("See Rule 21.", [({"number": "2", "title": "", "page_start": 1, "page_end": 1, "text": ""}, 0)]) == [])

    # 4. Search with the real data, if it is here.
    try:
        engine = RuleSearch(load_rules())
    except Exception as e:  # data folder missing
        skip("search", "Rule 2(5)(c) puts Rule 2 first", f"data not loaded: {e}")
        return None
    top = [r["number"] for r, _ in engine.search("What does Rule 2(5)(c) say?", k=3)]
    record("search", "Rule 2(5)(c) puts Rule 2 first", top[:1] == ["2"], f"-> {top}")
    return engine


# ---------------------------------------------------------------- live checks (the 10 manual questions)
# exp_rules: ANY of these must be among the retrieved rules AND be named in the answer.
# values: every string must appear in the answer (only where the team read the PDF table).
CASES = [
    dict(id="M1", q="My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?",
         rules=["56"], values=["3.6"], table_note=True),
    dict(id="M2", q="I applied for building permission and the authority has not replied. What happens if they miss the deadline?",
         rules=["28"]),
    dict(id="M3", q="How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?",
         rules=["52"], table_note=True),
    dict(id="M4", q="मेरा मकान 9 मीटर ऊँचा है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह छोड़नी होगी?", lang="hi",
         rules=["56"], values=["3.0"], hindi=True),
    dict(id="M5", q="How do I pay my property tax online?", not_found=True),
    dict(id="M6", q="What documents go with an application for building permission?",
         rules=["16", "14"], list_note=True),
    dict(id="M7", q="What is the maximum height of a building?", rules=["42"], table_note=True),
    dict(id="M8", q="What is the current market rate for land in Kolar Road, Bhopal?", not_found=True),
    dict(id="M9", q="Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
         amendment="2-5-c"),   # either answered or NOT_FOUND is fine, but the amendment box must show
    dict(id="M10", q="मैं अपना प्रॉपर्टी टैक्स ऑनलाइन कैसे जमा करूँ?", lang="hi", not_found=True),
]


def run_case(c, engine, client):
    for i in range(3):
        try:
            return A.answer(c["q"], engine, c=client, lang=c.get("lang"))
        except Exception:
            if i == 2:
                raise
            time.sleep(3)


def live(engine):
    if engine is None:
        skip("live", "all", "rule data not loaded")
        return
    client = A.client()
    for c in CASES:
        try:
            res = run_case(c, engine, client)
        except Exception as e:
            record("live", c["id"], False, f"error: {e}")
            continue
        ans, nums = res["answer"], [s[0] for s in res["sources"]]
        problems = []
        if c.get("not_found") and not res["not_found"]:
            problems.append(f"should be NOT_FOUND but answered: {ans[:80]!r}")
        if c.get("rules"):
            if res["not_found"]:
                problems.append("NOT_FOUND but a rule answer was expected")
            else:
                if not any(r in nums for r in c["rules"]):
                    problems.append(f"expected rule {c['rules']} not retrieved (got {nums})")
                if not any(re.search(rf"\bRule {re.escape(r)}\b", ans) for r in c["rules"]):
                    problems.append(f"expected rule {c['rules']} not named in answer")
        for v in c.get("values", []):
            if v not in ans:
                problems.append(f"value {v} missing from answer")
        if c.get("hindi") and not A.has_devanagari(ans):
            problems.append("answer is not in Hindi")
        if c.get("table_note") and not any(n.startswith("TABLE") for n in res["notes"]):
            problems.append("no TABLE warning")
        if c.get("list_note") and not any(n.startswith("LIST") for n in res["notes"]):
            problems.append("no LIST warning")
        if c.get("amendment") and c["amendment"] not in [a["id"] for a in res["amendments"]]:
            problems.append(f"amendment {c['amendment']} not shown")
        if c.get("amendment") and res["not_found"] and not res["not_found_note"]:
            problems.append("NOT_FOUND with an amendment but no note")
        if not res["not_found"] and not res["cited"]:
            problems.append("answer names no retrieved rule (no PDF page to show)")
        record("live", c["id"], not problems, "; ".join(problems))


def main():
    engine = offline()
    if "--live" in sys.argv:
        live(engine)
    else:
        print("\n(Offline run. Add --live to test the 10 questions through Claude.)")

    n = {s: sum(1 for r in results if r[2] == s) for s in (PASS, FAIL, SKIP)}
    print(f"\nPASS {n[PASS]}   FAIL {n[FAIL]}   SKIP {n[SKIP]}")
    with open("regression_results.md", "w", encoding="utf-8") as f:
        f.write("# Regression results\n\n"
                "Behaviour checks only. They do not prove legal correctness; check numbers against the PDF.\n\n"
                f"PASS {n[PASS]}, FAIL {n[FAIL]}, SKIP {n[SKIP]}\n\n"
                "| Group | Case | Status | Detail |\n|---|---|---|---|\n")
        for g, name, st, d in results:
            f.write(f"| {g} | {name[:70].replace('|', '/')} | {st} | {d[:160].replace('|', '/')} |\n")
    print("Saved: regression_results.md")
    sys.exit(1 if n[FAIL] else 0)


if __name__ == "__main__":
    main()

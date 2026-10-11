"""Full accuracy check. Needs the API key. Takes a few minutes.

    python eval_full.py

For every question it checks:
  retrieved : the expected rule is among the rules given to Claude
  cited     : the answer names the expected rule ("Rule 56")
  numbers   : (table questions only) the right value is in the answer
  quotes    : every quoted line really appears in a retrieved rule's text
  not_found : out-of-scope questions get NOT_FOUND

Expected values for the front-setback table come from Rule 56(1)(a) in the PDF
(buildings up to 12.5 m: street up to 9.0 m = 3.0, over 9.0 to 12 = 3.6, over 12 to 18 = 4.5, above 18 = 6.0).
The expected rules for the 17 sample questions come from eval.py. Check a few answers by hand against the PDF.
Results are also saved in eval_results.md so you can paste them into the README.
"""
import re
import time

import answer as A
from eval import QUESTIONS
from search import RuleSearch, load_rules
from verify import corpus_for, find_quotes, match_quote_ex

# (question, expected value that must appear in the answer)  -- all Rule 56(1)(a), height up to 12.5 m
TABLE = [
    ("My house is 9 m tall and faces an 8 m wide street. How much front open space do I leave?", "3.0"),
    ("My house is 9 m tall and faces a 9 m wide street. How much front open space do I leave?", "3.0"),
    ("My house is 9 m tall and faces a 10 m wide street. How much front open space do I leave?", "3.6"),
    ("My house is 9 m tall and faces a 12 m wide street. How much front open space do I leave?", "3.6"),
    ("My house is 9 m tall and faces a 15 m wide street. How much front open space do I leave?", "4.5"),
    ("My house is 9 m tall and faces a 20 m wide street. How much front open space do I leave?", "6.0"),
    ("मेरा मकान 9 मीटर ऊँचा है और सामने 15 मीटर चौड़ी सड़क है। आगे कितनी जगह छोड़नी होगी?", "4.5"),
    ("mera ghar 9 m ooncha hai aur saamne 20 m chaudi sadak hai, aage kitni jagah chhodni hogi", "6.0"),
]
ALL_VALUES = ["3.0", "3.6", "4.5", "6.0"]


def check_quotes(res, by_num):
    corpus = corpus_for(by_num, [n for n, *_ in res["sources"]])
    qs = find_quotes(res["answer"])
    results = [match_quote_ex(q, corpus) for q in qs]
    bad = [q for q, r in zip(qs, results) if r[0] is None]
    loose = sum(1 for r in results if r[1] == "table")
    return len(qs) - len(bad), len(qs), bad, loose


def answer_with_retry(q, engine, c, tries=3):
    for i in range(tries):
        try:
            return A.answer(q, engine, c=c)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3)


def main():
    engine = RuleSearch(load_rules())
    by_num = {r["number"]: r for r in engine.rules}
    c = A.client()

    cases = [(f"Q{i}", q, exp, None) for i, q, exp in QUESTIONS]
    cases += [(f"T{i + 1}", q, ["56"], v) for i, (q, v) in enumerate(TABLE)]

    stats = dict(ret=[0, 0], cit=[0, 0], num=[0, 0], nf=[0, 0], qok=0, qtot=0, err=0, loose=0)
    rows, problems = [], []

    for cid, q, exp, value in cases:
        try:
            res = answer_with_retry(q, engine, c)
        except Exception as e:
            stats["err"] += 1
            rows.append((cid, q, "ERROR", str(e)[:60]))
            problems.append(f"{cid}: error {e}")
            print(f"{cid}: ERROR {e}")
            continue

        ans = res["answer"]
        nums = [s[0] for s in res["sources"]]

        if exp == []:
            stats["nf"][1] += 1
            ok = res["not_found"]
            stats["nf"][0] += ok
            flag = "OK" if ok else "WRONG (answered)"
            rows.append((cid, q, "NOT_FOUND expected", flag))
            if not ok:
                problems.append(f"{cid}: should be NOT_FOUND but answered: {ans[:90]}")
            print(f"{cid}: not-found check -> {flag}")
            continue
        if exp is None:
            print(f"{cid}: skipped (no expected rule)")
            continue

        ret = any(e in nums for e in exp)
        cit = (not res["not_found"]) and any(re.search(rf"\bRule {re.escape(e)}\b", ans) for e in exp)
        stats["ret"][1] += 1; stats["ret"][0] += ret
        stats["cit"][1] += 1; stats["cit"][0] += cit
        note = []
        if value:
            num_ok = value in ans
            stats["num"][1] += 1; stats["num"][0] += num_ok
            extra = [v for v in ALL_VALUES if v != value and v in ans]
            note.append(f"value {value}: {'OK' if num_ok else 'MISSING'}" + (f" (also mentions {extra})" if extra else ""))
            if not num_ok:
                problems.append(f"{cid}: expected {value} in answer: {ans[:120]}")
        qo, qt, bad, lo = check_quotes(res, by_num)
        stats["loose"] += lo
        stats["qok"] += qo; stats["qtot"] += qt
        if qt and qo < qt:
            note.append(f"{qt - qo} quote(s) not matched")
        if not ret:
            problems.append(f"{cid}: expected rule {exp} not retrieved (got {nums})")
        elif not cit:
            problems.append(f"{cid}: rule {exp} retrieved but not cited. Answer starts: {ans[:160]!r}")
        for b_ in bad[:3]:
            problems.append(f"{cid}: quote not found in rule text: {b_[:110]!r}")
        status = f"retrieved={'Y' if ret else 'N'} cited={'Y' if cit else 'N'}"
        rows.append((cid, q, status, "; ".join(note)))
        print(f"{cid}: {status}  {'; '.join(note)}")

    def pct(a):
        return f"{a[0]}/{a[1]}" + (f" ({100 * a[0] // a[1]}%)" if a[1] else "")

    summary = [
        f"Expected rule retrieved (top {A.__dict__.get('K', 8)}+): {pct(stats['ret'])}",
        f"Expected rule cited in the answer: {pct(stats['cit'])}",
        f"Right table value in the answer (Rule 56 front open space): {pct(stats['num'])}",
        f"Quoted lines found in the rule text: {stats['qok']}/{stats['qtot']} ({stats['loose']} matched only as flattened table text)",
        f"Not-found on out-of-scope questions: {pct(stats['nf'])}",
        f"Errors: {stats['err']}",
    ]
    print("\n" + "\n".join(summary))
    if problems:
        print("\nLook at these by hand:")
        for p in problems:
            print(" -", p)

    with open("eval_results.md", "w", encoding="utf-8") as f:
        f.write("# Accuracy results\n\n" + "\n".join(f"- {s}" for s in summary) + "\n\n")
        f.write("| Case | Question | Result | Note |\n|---|---|---|---|\n")
        for cid, q, st, nt in rows:
            f.write(f"| {cid} | {q[:70].replace('|', '/')} | {st} | {nt} |\n")
        if problems:
            f.write("\n## To check by hand\n" + "\n".join(f"- {p}" for p in problems) + "\n")
    print("\nSaved: eval_results.md")


if __name__ == "__main__":
    main()

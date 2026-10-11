"""Measure how often retrieval finds the right rule on the 17 sample questions.

Step 1 (no API key needed):   python eval.py
Step 2 (needs API key):       python eval.py --answers     (also checks NOT_FOUND on Q16, Q17)

Fill the EXPECTED rule numbers yourself by checking the PDF. Leave None if unsure.
A question counts as a hit if ANY expected rule is in the top 5 results.
Hindi questions (14, 15) need the API key because they are translated first.
"""
import sys

from search import RuleSearch, load_rules

# (id, question, expected rule numbers as strings, or None = fill in, [] = should be NOT_FOUND)
QUESTIONS = [
    (1, "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?", ["56"]),
    (2, "I want a farm house on agricultural land. What is the minimum plot size and the maximum FAR?", ["17"]),
    (3, "My development permission was granted in 2023. How long does it stay valid, and how many times can I renew it?", ["23"]),
    (4, "I applied for building permission and the authority has not replied. What happens if they miss the deadline?", ["28"]),
    (5, "How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?", ["52"]),
    (6, "Who is allowed to sign and submit my building plans?", ["18", "26"]),
    (7, "What documents go with an application for building permission?", ["16", "14"]),
    (8, "What is the fee for building permission for a residential house?", ["21"]),
    (9, "Can I change my plan after it is sanctioned?", ["24"]),
    (10, "What is the minimum rear open space for a 150 sq m residential plot?", ["56"]),
    (11, "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?", ["2", "12"]),
    (12, "Which rule decides what happens when the Development Plan and these rules disagree?", ["103"]),
    (13, "What are the rules for lifts in a building taller than 15 m?", ["83"]),
    (14, "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?", ["56"]),
    (15, "बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है?", ["21"]),
    (16, "How do I pay my property tax online?", []),
    (17, "What is the current market rate for land in Kolar Road, Bhopal?", []),
]


TOPK = 8   # answer.py also gives Claude the top 8 rules


def main():
    use_answers = "--answers" in sys.argv
    engine = RuleSearch(load_rules())
    c = None
    if use_answers:
        import answer as A
        c = A.client()

    hits = total = 0
    nf_ok = nf_total = 0
    for qid, q, expected in QUESTIONS:
        is_hindi = any("ऀ" <= ch <= "ॿ" for ch in q)
        if use_answers:
            res = A.answer(q, engine, c=c)
            got = [s[0] for s in res["sources"]]
        elif is_hindi:
            print(f"Q{qid}: skipped (Hindi needs --answers)")
            continue
        else:
            got = [r["number"] for r, _ in engine.search(q, k=TOPK)]
            res = None

        if expected == []:
            if res is not None:
                nf_total += 1
                ok = res["not_found"]
                nf_ok += ok
                print(f"Q{qid}: should be NOT_FOUND -> {'OK' if ok else 'WRONG (tool answered)'}")
            else:
                print(f"Q{qid}: should be NOT_FOUND (run --answers to check)")
            continue

        status = "?"
        if expected:
            total += 1
            ok = any(e in got for e in expected)
            hits += ok
            status = "HIT" if ok else "MISS"
        print(f"Q{qid}: {status}  expected={expected}  top={got}")

    print()
    if total:
        print(f"Retrieval: {hits}/{total} questions have the expected rule in top {TOPK}")
    else:
        print("Fill in EXPECTED rule numbers in eval.py to get a score.")
    if nf_total:
        print(f"Not-found handling: {nf_ok}/{nf_total}")


if __name__ == "__main__":
    main()

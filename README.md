# Bhumi Vikas Sahayak

**Track 1, Claude Impact Lab × Cerebras Café Compute, Bhopal, 11 October 2026**

- **Team:** TEAM NAME HERE
- **Members:** NAMES HERE

## The one user

A building-permission clerk at the Bhopal Municipal Corporation counter. A citizen asks
"My plot is 200 sq m on a 9 m road. How much gap do I leave at the front?" and the clerk needs
the answer in a minute, with the rule number to show the citizen.

## What it does

The clerk types a question in English, Hindi or Hinglish. The tool finds the matching rules in the
MP Bhumi Vikas Rules, 2012 (consolidated to 6 March 2025) and shows:

- a short answer (in Hindi if the page is set to Hindi, otherwise in the language of the question)
- the rule number and the exact rule text it came from
- a tick next to every quoted line that was found in the rule text, and a warning if it was not
- the PDF page range, and the page image, so the clerk can check the original
- "Not found in the rulebook" when the rules are silent. It does not guess.
- the rules version on every answer, and a box for changes made after March 2025
- a printable slip for the citizen

The tool points to the rule. The clerk decides. It is not legal advice.

## How it works

1. `search.py` loads the 106 rules and ranks them with BM25 (keyword search, light stemming, a small
   synonym list such as "deadline" to "limitation period").
2. `answer.py` splits multi-part and Hindi/Hinglish questions into short English search queries, gives the
   top rules to Claude, which may use only those rules, must quote the rule text and number, and must reply
   `NOT_FOUND` if the rules do not answer.
3. `verify.py` checks every quoted line against the retrieved rule text. It accepts exact matches
   (ignoring PDF page headers and footnote markers) and quotes taken from flattened tables, where another
   column's text sits between the words. Those are marked "(table text)". Paraphrases are not accepted.
4. `amendments.json` holds changes made after March 2025. A matching change is shown above the answer.
5. `server.py` + `index.html` are the web page (English / Hindi switch). `app.py` is an older Streamlit page that still works.

## Run it (5 steps)

1. `git clone` this repo and open a terminal in the folder. Put the data pack's `data/` folder and the English PDF
   (`resources/MP_Bhumi_Vikas_Rules_2012_upto_2025-03-06_EN.pdf`) in it if they are not there.
2. `pip install -r requirements.txt`
3. Put your key in a file called `.env`: `ANTHROPIC_API_KEY=your_key` (or set it as an environment variable).
4. `python server.py`
5. Open http://localhost:8000 (it opens by itself). Streamlit version: `streamlit run app.py`.

## How often is it right

`python eval_full.py` runs 23 questions: the 15 sample questions that have a rulebook answer, plus 8 extra
front-setback questions (6 English, 1 Hindi, 1 Hinglish) whose right value we read from the Rule 56(1)(a) table.
It also runs the 2 out-of-scope sample questions. Full table: `eval_results.md`.

| Check | Result |
|---|---|
| Right rule among the rules given to Claude | 23 of 23 |
| Right rule named in the answer | 23 of 23 |
| Right front-setback value in the answer (Rule 56 table) | 8 of 8 |
| Quoted lines found in the rule text | 85 of 87 (4 of them only as flattened table text) |
| "Not found" on the 2 out-of-scope questions (Q16, Q17) | 2 of 2 |
| Answers read and checked by hand against the PDF | FILL IN |

How to read this: it is one run on 25 questions. It checks that the right rule was found, named and quoted
correctly. It does not prove that every answer's meaning is right. The expected rule numbers for the sample
questions were found by reading the rule text; the Rule 56 values were checked against the PDF table.
Answers can differ a little between runs: on an earlier run Q11 came back as "not found", on the latest run it
was answered with Rule 2 and Rule 12.

## What works and what doesn't

Works:
- English, Hindi and Hinglish questions, answered with rule numbers and exact text.
- Not-found handling for questions outside the rulebook.
- Quote check on every answer. Two quotes in the latest run were flagged (Q5, Q8: table rows where the cells
  were joined). They need a look at the PDF. The tool shows them with a warning instead of hiding them.

Does not work yet or needs care:
- **Changes after 6 March 2025 are not in the rule text.** `amendments.json` lists three (28 Aug 2026 change to
  Rule 2(5)(c); 15 Dec 2025 green-building FAR; a June 2026 draft on land uses, which is only a draft). They come from
  TeamLease RegTech summaries, not from the gazette text. The tool shows them next to the answer; the rule text itself
  is still the March 2025 version.
- Q11 (300 sq m plot, development permission) is the least stable answer. The search does not rank Rule 2 or 12
  first, so the app always adds them on that topic. This is a patch, not a general fix.
- Tables are flattened text. Check any fee or setback number against the PDF page shown.
- The tool does not calculate fees or areas. A clerk should calculate from the table shown.
- Search is keyword-based, so unusual wording can miss the right rule. Hinglish is recognised from a word list,
  so a Hinglish question with none of those words is treated as English.
- The quote check shows that a quoted line is in the rule text. It does not check that Claude read it correctly.
- For questions the rules do not cover there is an optional button, "general information (not from the rules)".
  It is off by default, is clearly labelled, and never gives rule numbers, fees or deadlines.
- The Hindi screen translates the page. The text of the amendment boxes is still English.
- Rules 12-A, 17-a, 25(A), 26-A, 42-A and 93(a) sit inside the text of the previous rule in the data, as in the data pack.

## Data

Track 1 data pack: https://github.com/Laaaaksh/bhopal-impact-lab-2026
(MP Bhumi Vikas Rules 2012, consolidated to 6 March 2025: https://mptownplan.gov.in/NewsPDF/bvn06032025E.pdf).

Extra public data (summaries of amendments, in `amendments.json`):
- 28 Aug 2026, Rule 2(5)(c): https://teamleaseregtech.com/updates/article/59469/government-of-madhya-pradesh-amendment-to-land-development-rules
- 15 Dec 2025, Rule 5(6) and Appendix M: https://teamleaseregtech.com/updates/article/50844/govt-of-madhya-pradesh-issued-amendments-to-the-madhya-pradesh-bhumi-vikas-niyam-2012/
- 29 Jun 2026 draft, Rule 37(1)(a): https://teamleaseregtech.com/updates/article/57899/draft-amendment-to-madhya-pradesh-bhumi-vikas-niyam-2012/

No personal data. No connection to any government system.

## License

MIT, see `LICENSE`.

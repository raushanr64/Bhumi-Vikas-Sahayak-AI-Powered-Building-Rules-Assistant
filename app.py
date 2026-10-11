"""Bhumi Vikas Sahayak: Streamlit page for the building-permission clerk.

Run:  streamlit run app.py
"""
import html
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

import answer as A
from search import RuleSearch, load_rules
from verify import corpus_for, find_quotes, match_quote_ex

HERE = Path(__file__).parent
PDF_PATH = HERE / "resources" / "MP_Bhumi_Vikas_Rules_2012_upto_2025-03-06_EN.pdf"

st.set_page_config(page_title="Bhumi Vikas Sahayak", page_icon="🏛️", layout="centered")


@st.cache_resource
def get_engine():
    return RuleSearch(load_rules())


def verify_quotes(answer_text, rules_by_num, source_nums):
    """[(quote, rule number or None, matched_only_as_table_text)] using verify.py."""
    corpus = corpus_for(rules_by_num, source_nums)
    out = []
    for q in find_quotes(answer_text):
        rule, kind = match_quote_ex(q, corpus)
        out.append((q, rule, kind == "table"))
    return out


@st.cache_data(show_spinner=False)
def render_page(page_no):
    import fitz  # PyMuPDF
    doc = fitz.open(str(PDF_PATH))
    return doc[int(page_no) - 1].get_pixmap(dpi=110).tobytes("png")


def build_slip(res, verified):
    ts = datetime.now().strftime("%d %b %Y, %H:%M")
    shown = res.get("cited") or res["sources"][:3]
    rules = ", ".join(f"Rule {n} (PDF p.{a}-{b})" for n, _, a, b in shown)
    body = html.escape(res["answer"]).replace("\n", "<br>")
    warn = f"<p><b>{html.escape(res['amendment_warning'])}</b></p>" if res["amendment_warning"] else ""
    notes = "".join(f"<p><b>Note:</b> {html.escape(n)}</p>" for n in res.get("notes", []))
    if res.get("not_found_note"):
        notes += f"<p><b>Note:</b> {html.escape(res['not_found_note'])}</p>"
    if not verified:
        ok = ""
    elif all(rule for _, rule, _ in verified):
        ok = "All quotes matched the rule text."
        if any(loose for _, _, loose in verified):
            ok += " Some matched only as flattened table text: check the PDF."
    else:
        ok = "Some quotes could not be matched. Check the PDF."
    return f"""<html><head><meta charset="utf-8"><title>Rule slip</title></head>
<body style="font-family:Arial;max-width:700px;margin:30px auto">
<h2>Bhopal Municipal Corporation: Rule Reference Slip</h2>
<p>{ts}</p><p><b>Question:</b> {html.escape(res['question'])}</p>
<p><b>Answer:</b><br>{body}</p><p><b>Rules:</b> {html.escape(rules)}</p>
<p><b>Version:</b> {html.escape(res['version'])}</p>{warn}{notes}<p>{ok}</p>
<hr><small>This slip points to the rule. It is not legal advice. The clerk decides.</small>
<script>window.print()</script></body></html>"""


# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Settings")
    if os.environ.get("ANTHROPIC_API_KEY"):
        st.success("API key found in environment.")
    else:
        key = st.text_input("Anthropic API key", type="password")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key.strip()
            st.rerun()
        else:
            st.warning("No API key found. Paste it above or use a .env file.")
    st.markdown(f"**Rules version:** {A.RULES_VERSION}")
    st.markdown("Changes after 6 March 2025 are not included, e.g. the 28 Aug 2026 amendment to Rule 2(5)(c).")

st.title("🏛️ Bhumi Vikas Sahayak")
st.caption("Ask the MP Bhumi Vikas Rules, 2012 in English or Hindi. Every answer shows the rule number "
           "and the exact rule text. This tool points to the rule; the clerk decides.")

EXAMPLES = [
    "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?",
    "I applied for building permission and the authority has not replied. What happens if they miss the deadline?",
    "How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?",
    "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?",
    "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
    "How do I pay my property tax online?",
]

st.markdown("**Try an example:**")
for i, ex in enumerate(EXAMPLES):
    label = ex if len(ex) <= 80 else ex[:78] + "..."
    if st.button(label, key=f"ex{i}", use_container_width=True):
        st.session_state["q"] = ex

question = st.text_area("Your question", key="q", height=110,
                        placeholder="Type the citizen's question in English or Hindi")

if st.button("Find the rule", type="primary"):
    if not question.strip():
        st.warning("Type a question first.")
    else:
        try:
            with st.spinner("Searching the rulebook..."):
                st.session_state["res"] = A.answer(question.strip(), get_engine())
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Something went wrong: {e}")

res = st.session_state.get("res")
if res:
    engine = get_engine()
    rules_by_num = {r["number"]: r for r in engine.rules}
    source_nums = [s[0] for s in res["sources"]]

    for am in res.get("amendments", []):
        st.warning(
            f"**Changed after March 2025: Rule {am['rule']}, {am['title']}**\n\n"
            f"Status: {am['status']}\n\n"
            f"What the change says: {am['now']}\n\n"
            f"Source: [{am['source_name']}]({am['source_url']}). This is a summary, "
            f"not the gazette text. The rule text below is the March 2025 version."
        )

    if res["not_found"]:
        st.info("Not found in the rulebook. The rules are silent on this. Do not guess; check with a senior.")
        if res.get("not_found_note"):
            st.warning(res["not_found_note"])
        verified = []
    else:
        st.success(res["answer"])
        verified = verify_quotes(res["answer"], rules_by_num, source_nums)
        for q, found, loose in verified:
            if found and loose:
                st.markdown(f"✅ **Found in Rule {found} (table text, check the PDF):** *{q[:140].strip()}*")
            elif found:
                st.markdown(f"✅ **Verified from Rule {found}:** *{q[:140].strip()}*")
            else:
                st.markdown(f"⚠️ **Not matched in retrieved rules. Check the PDF:** *{q[:140].strip()}*")
        if res.get("cited"):
            st.markdown("**Cited rules:** " + "; ".join(
                f"Rule {n} (PDF p.{a}-{b})" for n, _, a, b in res["cited"]))
        for note in res.get("notes", []):
            st.warning(note)

    st.caption(f"Version: {res['version']}  |  Search query used: {res['search_query']}")

    st.subheader("Retrieved rules")
    cited_nums = {n for n, *_ in res.get("cited", [])}
    ordered = sorted(res["sources"], key=lambda s_: s_[0] not in cited_nums)  # cited rules first
    for n, title, a, b in ordered:
        tag = "  [cited]" if n in cited_nums else ""
        with st.expander(f"Rule {n}: {title}  (PDF p.{a}-{b}){tag}"):
            st.text(rules_by_num[n]["text"])   # full text, not cut
            if PDF_PATH.exists():
                try:
                    last = min(int(b), int(a) + 2)          # show up to 3 pages of the rule
                    for pg in range(int(a), last + 1):
                        st.image(render_page(pg), caption=f"Official PDF, page {pg}")
                    if int(b) > last:
                        st.caption(f"Rule continues to PDF page {b}. Open it in the PDF.")
                except Exception as e:
                    st.caption(f"Could not render PDF page ({e}). Open page {a} manually.")
            else:
                st.caption(f"PDF not found in resources/. Open PDF pages {a}-{b} manually.")

    st.download_button("🖨️ Download citizen slip (open and print)",
                       build_slip(res, verified), file_name="rule_slip.html", mime="text/html")

"""Bhumi Vikas Sahayak: Streamlit page for the building-permission clerk.

Run locally:  streamlit run app.py
On Streamlit Community Cloud: put  ANTHROPIC_API_KEY = "sk-ant-..."  in the app's Secrets.

This page calls answer.py directly, so no separate server is needed.
(server.py + index.html are the alternative web page for running on your own machine.)
"""
import os

import streamlit as st

import answer as A
from search import RuleSearch, load_rules
from verify import corpus_for, find_quotes, match_quote_ex

st.set_page_config(page_title="Bhumi Vikas Sahayak", page_icon="🏛️", layout="centered")

# On Streamlit Community Cloud the key lives in the app's Secrets, not in a .env file.
try:
    if not os.environ.get("ANTHROPIC_API_KEY") and "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = str(st.secrets["ANTHROPIC_API_KEY"]).strip()
except Exception:
    pass  # no secrets configured: the sidebar box below is used instead


@st.cache_resource
def get_engine():
    return RuleSearch(load_rules())


engine = get_engine()
by_number = {r["number"]: r for r in engine.rules}

EXAMPLES = {
    "en": [
        "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?",
        "I applied for building permission and the authority has not replied. What happens if they miss the deadline?",
        "How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?",
        "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
        "How do I pay my property tax online?",
    ],
    "hi": [
        "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?",
        "बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है?",
        "300 वर्ग मीटर के प्लॉट पर अलग से विकास अनुज्ञा लेनी होगी क्या?",
    ],
}


def verify_quotes(text, source_nums):
    """Each quoted passage in the answer must appear in one of the retrieved rules."""
    corpus = corpus_for(by_number, source_nums)
    out = []
    for q in find_quotes(text):
        rule, kind = match_quote_ex(q, corpus)
        out.append({"text": q, "rule": rule, "loose": kind == "table"})
    return out


def friendly_error(e):
    name = type(e).__name__
    if isinstance(e, RuntimeError):
        return str(e)
    if "Authentication" in name:
        return "The API key was rejected (401). Check the key in Secrets or in the sidebar."
    if "RateLimit" in name or "Overloaded" in name:
        return "The service is busy. Wait a few seconds and press the button again."
    if "Connection" in name or "Timeout" in name:
        return "Could not reach the Claude API in time. Press the button again."
    return f"Something went wrong ({name}). Please try again."


st.title("🏛️ Bhumi Vikas Sahayak")
st.caption(
    "Ask the MP Bhumi Vikas Rules, 2012 in English or Hindi. "
    "Every answer shows the rule number and the exact rule text. "
    "This tool points to the rule; the clerk decides."
)

with st.sidebar:
    st.header("Settings")
    lang_label = st.radio("Language / भाषा", ["English", "हिन्दी"], horizontal=True)
    lang = "hi" if lang_label == "हिन्दी" else "en"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        key = st.text_input("Anthropic API key", type="password",
                            help="Kept only in this browser session. Not saved anywhere.")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key.strip()
    else:
        st.success("API key is set.")
    st.markdown(f"**Rules version:** {A.RULES_VERSION}")
    st.markdown("Changes after 6 March 2025 are not in the rule text. "
                "The tool shows a warning box when a known later change may apply.")

st.write("**Try an example:**" if lang == "en" else "**उदाहरण चुनें:**")
for i, ex in enumerate(EXAMPLES[lang]):
    if st.button(ex[:90] + ("..." if len(ex) > 90 else ""), key=f"ex_{lang}_{i}", use_container_width=True):
        st.session_state["q"] = ex

question = st.text_area(
    "Your question" if lang == "en" else "आपका सवाल", key="q", height=100,
    placeholder="Type the citizen's question in English or Hindi",
)

if st.button("Find the rule" if lang == "en" else "नियम खोजें", type="primary") and question.strip():
    try:
        with st.spinner("Searching the rulebook..." if lang == "en" else "नियम-पुस्तिका में खोज रहे हैं..."):
            st.session_state["res"] = A.answer(question.strip(), engine, lang=lang)
    except Exception as e:
        st.session_state.pop("res", None)
        st.error(friendly_error(e))
        with st.expander("Technical details"):
            st.code(f"{type(e).__name__}: {str(e)[:400]}")

res = st.session_state.get("res")
if res:
    st.divider()
    if res["not_found"]:
        st.warning("**Not found in the rulebook.** The rules do not answer this question. "
                   "Please check with your senior or the department.")
        if res.get("not_found_note"):
            st.info(res["not_found_note"])
    else:
        st.markdown(res["answer"])

    for a in res.get("amendments", []):
        with st.container(border=True):
            st.markdown(f"**Later change: Rule {a['rule']}, {a['date']}** ({a['status']})")
            st.write(a["now"])
            st.caption(f"Source: [{a['source_name']}]({a['source_url']}). "
                       "This is a summary, not the notification itself. Check the latest notification.")

    for n in res.get("notes", []):
        st.warning(n)

    nums = [s[0] for s in res["sources"]]
    if not res["not_found"]:
        quotes = verify_quotes(res["answer"], nums)
        if quotes:
            bad = [q for q in quotes if not q["rule"]]
            if bad:
                st.warning(f"{len(bad)} quoted passage(s) could not be matched to the retrieved rule text. "
                           "Check them on the PDF page.")
            else:
                st.caption(f"✓ All {len(quotes)} quoted passages were found in the retrieved rule text.")

    st.caption(f"Rules version: {res['version']}")

    st.subheader("Rules checked")
    st.caption("Open the PDF at the page shown to verify. Numbers in tables must be checked against the PDF.")
    for number, title, p1, p2 in res["sources"]:
        with st.expander(f"Rule {number}: {title} (PDF pages {p1}-{p2})"):
            st.text(by_number[number]["text"][:6000])
    with st.expander("Search query used"):
        st.write(res["search_query"])

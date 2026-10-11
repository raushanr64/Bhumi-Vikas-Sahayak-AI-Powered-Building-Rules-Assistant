"""Bhumi Vikas Sahayak: Streamlit app. Shows the index.html interface; the answers come from Python.

How it works: index.html runs inside Streamlit as a component. When the clerk presses "Find the rule",
index.html sends the question to this file, this file calls the same ask() function that server.py uses,
and the answer is sent back to index.html to draw. No separate web server is needed.

Run locally:  streamlit run app.py
Streamlit Community Cloud: put  ANTHROPIC_API_KEY = "sk-ant-..."  in the app's Secrets.
(For the plain web page without Streamlit, run  python server.py  instead.)
"""
import os
import shutil
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Bhumi Vikas Sahayak", page_icon="🏛️", layout="wide")

# On Streamlit Community Cloud the key lives in the app's Secrets, not in a .env file.
try:
    if not os.environ.get("ANTHROPIC_API_KEY") and "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = str(st.secrets["ANTHROPIC_API_KEY"]).strip()
except Exception:
    pass  # no secrets configured: the key box below is used instead

import server as S  # noqa: E402  (same ask() as the local web page)

HERE = Path(__file__).parent


@st.cache_resource
def get_frontend():
    """Register index.html as a Streamlit component (a copy in a temp folder, so index.html stays in one place)."""
    folder = Path(tempfile.mkdtemp(prefix="bvs_frontend_"))
    shutil.copy(HERE / "index.html", folder / "index.html")
    return components.declare_component("bvs_frontend", path=str(folder))


def friendly_error(e):
    name = type(e).__name__
    if isinstance(e, RuntimeError):
        return str(e)
    if "Authentication" in name:
        return "The API key was rejected (401). Check the key in Secrets or in the key box."
    if "RateLimit" in name or "Overloaded" in name:
        return "The service is busy. Wait a few seconds and press the button again."
    if "Connection" in name or "Timeout" in name:
        return "Could not reach the Claude API in time. Press the button again."
    return f"Something went wrong ({name}). Please try again."


def handle(req):
    """Turn one request from index.html into the response it expects."""
    try:
        question = (req.get("question") or "").strip()
        if not question:
            return {"id": req["id"], "status": 400, "data": {"error": "Type a question first."}}
        return {"id": req["id"], "status": 200, "data": S.ask(question, req.get("lang"))}
    except Exception as e:  # always answer, so the page never waits forever
        return {"id": req["id"], "status": 500, "data": {"error": friendly_error(e)}}


if not os.environ.get("ANTHROPIC_API_KEY"):
    with st.expander("API key needed", expanded=True):
        key = st.text_input("Anthropic API key", type="password",
                            help="Kept only in this browser session. Not saved anywhere.")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key.strip()
            st.rerun()

frontend = get_frontend()
req = frontend(
    response=st.session_state.get("bvs_response"),
    request=st.session_state.get("bvs_request"),
    key="bvs",
    default=None,
)

if isinstance(req, dict) and req.get("id") and req["id"] != st.session_state.get("bvs_done"):
    st.session_state["bvs_done"] = req["id"]
    st.session_state["bvs_request"] = {"question": req.get("question", ""), "lang": req.get("lang", "en")}
    st.session_state["bvs_response"] = handle(req)
    st.rerun()

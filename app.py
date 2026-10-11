
"""Bhumi Vikas Sahayak — Streamlit HTML frontend loader."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

HERE = Path(__file__).parent
HTML_PATH = HERE / "index.html"

st.set_page_config(
    page_title="Bhumi Vikas Sahayak",
    page_icon="🏛️",
    layout="wide",
)

if not HTML_PATH.exists():
    st.error("index.html not found. Ensure it is in the repository root.")
    st.stop()

html_content = HTML_PATH.read_text(encoding="utf-8")

components.html(
    html_content,
    height=1200,
    scrolling=True,
)

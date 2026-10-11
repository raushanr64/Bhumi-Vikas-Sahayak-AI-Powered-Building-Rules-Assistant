"""Local server for the HTML front end. No extra packages needed (standard library only).

Run:   python server.py
Open:  http://localhost:8000
The API key is read from the environment or the local .env file (see answer.py).
"""
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import answer as A
from search import RuleSearch, load_rules
from verify import corpus_for, find_quotes, match_quote_ex

HERE = Path(__file__).parent
PDF_PATH = HERE / "resources" / "MP_Bhumi_Vikas_Rules_2012_upto_2025-03-06_EN.pdf"
PORT = 8000

ENGINE = RuleSearch(load_rules())
BY_NUM = {r["number"]: r for r in ENGINE.rules}
_page_cache = {}


def verify_quotes(text, source_nums):
    """Each quoted passage in the answer must appear in one of the retrieved rules."""
    corpus = corpus_for(BY_NUM, source_nums)
    out = []
    for q in find_quotes(text):
        rule, kind = match_quote_ex(q, corpus)
        out.append({"text": q, "rule": rule, "loose": kind == "table"})
    return out


def ask(question, lang=None):
    res = A.answer(question, ENGINE, lang=lang)
    nums = [s[0] for s in res["sources"]]
    return {
        "question": res["question"],
        "search_query": res["search_query"],
        "answer": res["answer"],
        "not_found": res["not_found"],
        "version": res["version"],
        "amendments": res.get("amendments", []),
        "quotes": [] if res["not_found"] else verify_quotes(res["answer"], nums),
        "sources": [
            {"number": n, "title": t, "page_start": a, "page_end": b, "text": BY_NUM[n]["text"][:6000]}
            for n, t, a, b in res["sources"]
        ],
    }


def render_page(n):
    if n not in _page_cache:
        import fitz  # PyMuPDF
        doc = fitz.open(str(PDF_PATH))
        _page_cache[n] = doc[n - 1].get_pixmap(dpi=110).tobytes("png")
    return _page_cache[n]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._json(200, {"live": True})
        elif path.startswith("/api/page/"):
            try:
                self._send(200, render_page(int(path.rsplit("/", 1)[1])), "image/png")
            except Exception:
                self._send(404, "page not available", "text/plain")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path not in ("/api/ask", "/api/general"):
            return self._send(404, "not found", "text/plain")
        try:
            size = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(size))
            question = body["question"].strip()
            lang = body.get("lang")
            if not question:
                return self._json(400, {"error": "Type a question first."})
            if self.path == "/api/general":
                return self._json(200, {"note": A.general_note(question, lang=lang)})
            self._json(200, ask(question, lang))
        except RuntimeError as e:  # missing API key
            self._json(500, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"Bhumi Vikas Sahayak running at {url}  (Ctrl+C to stop)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

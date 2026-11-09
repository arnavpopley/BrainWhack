"""The hosted BrainWhack lab on Vercel.

Vercel functions can't stream, so /api/breed runs a whole breed in one request and
returns sampled frames that the page replays. Locally, whack_lab.py streams live instead.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir("/tmp")  # whack() writes its file to the current folder, and /tmp is the only writable one
from whack import WORDS, whack  # noqa: E402
from brainwhack import DOCS, FAMILY, breed_batch, load, run  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        route = query.get("route", [url.path.rstrip("/").rsplit("/", 1)[-1]])[0]
        if route == "words":
            body = {"words": WORDS, "family": FAMILY, "docs": DOCS}
        elif route == "wild":
            words = whack()
            prog = load("whack")  # the program is read back from the file whack() wrote
            prog = prog if prog == words else words
            trace = []
            out, ending, steps = run(prog, trace=trace, trace_limit=240)
            body = {"program": prog, "trace": trace, "ending": ending, "steps": steps, "out": list(out)}
        elif route == "breed":
            body = {"events": breed_batch(query.get("target", [""])[0])}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

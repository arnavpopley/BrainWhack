"""BrainWhack Lab: watch whack() breed a program, live in the browser.

    python3 whack_lab.py      then open http://localhost:8026

The breeder runs here in Python and streams every generation to the page.
Open http://localhost:8026/?breed=HONK to start breeding straight away.
"""
import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # whack() writes its file next to this script
from whack import WORDS, whack  # noqa: E402
from brainwhack import DOCS, FAMILY, INDEX, WhackRandom, breed_batch, evolve, run, save, whack_target  # noqa: E402

PORT = int(os.environ.get("PORT", 8026))


def payload(ev):
    """Makes an evolve() event JSON-friendly. The gene pool travels as word indices."""
    ev = dict(ev)
    for key in ("out", "target", "stuck_on"):
        if key in ev:
            ev[key] = list(ev[key])
    if "ranked" in ev:
        ev["pool"] = [[INDEX[w] for w in p] for p in ev.pop("ranked")]
    return ev


class Lab(SimpleHTTPRequestHandler):
    def send_json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/words":
            return self.send_json({"words": WORDS, "family": FAMILY, "docs": DOCS})
        if url.path == "/api/wild":
            return self.wild()
        if url.path == "/api/breed" and "batch" in url.query:  # the hosted page's replay mode
            return self.send_json({"events": breed_batch(parse_qs(url.query).get("target", [""])[0])})
        if url.path == "/api/breed":
            return self.breed(parse_qs(url.query).get("target", [""])[0], "fast" not in url.query)
        return super().do_GET()

    def wild(self):
        """One raw whack(), run as a program. The program is read back from the whack file."""
        words = whack()
        with open("whack", encoding="utf-8") as f:
            prog = f.read().split()
        if prog != words:  # another tab was breeding and rewrote the file in between
            prog = words
        trace = []
        out, ending, steps = run(prog, trace=trace, trace_limit=240)
        self.send_json({"program": prog, "trace": trace, "ending": ending, "steps": steps, "out": list(out)})

    def breed(self, target, watchable=True):
        rng = WhackRandom()
        target = "".join(c for c in target if 32 <= ord(c) < 127)[:8]
        chosen = not target
        if chosen:
            target = whack_target(rng)
        print(f"breeding {target!r}" + (" (whack() chose it)" if chosen else ""))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def send(obj):
            self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
            self.wfile.flush()

        try:
            send({"type": "start", "target": target, "chosen_by_whack": chosen})
            last = 0.0
            for ev in evolve(target, rng):
                if ev["type"] != "gen" or time.time() - last > 0.045:  # about 20 frames a second
                    last = time.time()
                    send(payload(ev))
                if watchable and ev["type"] == "gen":  # slow enough to follow; ?fast skips this
                    time.sleep(2.0 if ev["gen"] == 1 else 0.012)
                if ev["type"] == "done":
                    print(f"  bred {target!r} in {ev['gen']:,} generations, {ev['calls']:,} calls to whack(): saved {save(ev)}")
        except (BrokenPipeError, ConnectionResetError):
            print("  tab closed, breeding stopped")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Lab)
    except OSError:
        sys.exit(f"Port {PORT} is busy. Is the lab already running? Or pick another: PORT=8027 python3 whack_lab.py")
    print(f"BrainWhack Lab on http://localhost:{PORT}   (or http://localhost:{PORT}/?breed=HONK)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLab closed. Honk.")

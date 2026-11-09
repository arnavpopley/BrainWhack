"""Serves the browser hacks and gives them a real whack().

Browsers can't write files, so this server calls Python's whack() for them.
GET /api/whack calls whack(), then reads the whack file it wrote back off disk.

    python3 whack_server.py     then open http://localhost:8026
"""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from whack import whack  # noqa: E402

PORT = 8026


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/whack"):
            words = whack()
            with open("whack", encoding="utf-8") as f:
                from_file = f.read().split()
            body = json.dumps({"words": from_file, "returned": words, "count": len(words)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        if "/api/whack" in self.path:
            print("whack() called by", self.headers.get("Referer", "?").rsplit("/", 1)[-1] or "index")


if __name__ == "__main__":
    print(f"Whack server on http://localhost:{PORT}  (music: /music.html  map: /map.html)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

"""Imperative shell: stdlib HTTP server exposing the search engine.

Zero dependencies — run with `python3 app.py` and open
http://localhost:8000

Routes:
  GET /                 search UI
  GET /api/search?q=&limit=&offset=
  GET /api/suggest?q=
  GET /health
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from search import build_index, search, suggest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "data", "movies.json"), encoding="utf-8") as f:
    INDEX = build_index(json.load(f))

with open(os.path.join(BASE_DIR, "static", "index.html"), encoding="utf-8") as f:
    HOME_PAGE = f.read().encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        url = urlparse(self.path)
        params = parse_qs(url.query)
        query = params.get("q", [""])[0]

        if url.path == "/":
            self._respond(200, "text/html; charset=utf-8", HOME_PAGE)
        elif url.path == "/api/search":
            limit = min(int(params.get("limit", ["10"])[0]), 50)
            offset = max(int(params.get("offset", ["0"])[0]), 0)
            started = time.perf_counter()
            payload = search(INDEX, query, limit=limit, offset=offset)
            payload["took_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self._json(payload)
        elif url.path == "/api/suggest":
            self._json({"suggestions": suggest(INDEX, query)})
        elif url.path == "/health":
            self._json({"status": "ok", "movies": len(INDEX.movies)})
        else:
            self._respond(404, "application/json", b'{"error": "not found"}')

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._respond(200, "application/json; charset=utf-8", body)

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Telugu movie search: http://localhost:{port} "
          f"({len(INDEX.movies)} movies, {len(INDEX.vocab)} terms indexed)")
    server.serve_forever()


if __name__ == "__main__":
    main()

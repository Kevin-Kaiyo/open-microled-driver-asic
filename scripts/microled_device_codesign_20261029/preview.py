#!/usr/bin/env python3
"""Local read-only report preview; only docs/evidence files, no private build data."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[2]


class PublicReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_head(self):
        path = Path(self.translate_path(self.path)).resolve()
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            self.send_error(403)
            return None
        if not rel.parts or rel.parts[0] not in {"docs", "evidence"}:
            self.send_error(403, "Only public report/evidence paths are served")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled; open an explicit report URL")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8772)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), PublicReportHandler)
    print(f"Preview http://127.0.0.1:{args.port}/docs/research/microled-device-codesign-20261029/index.html", flush=True)
    server.serve_forever()

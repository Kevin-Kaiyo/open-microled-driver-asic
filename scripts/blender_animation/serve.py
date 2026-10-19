"""Local research viewer with HTTP byte ranges for native MP4 seeking."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import os
import re


class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def send_head(self):
        self._byte_range = None
        value = self.headers.get('Range')
        path = Path(self.translate_path(self.path))
        if not value or not path.is_file():
            return super().send_head()
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value.strip())
        with path.open('rb') as source:
            stat = os.fstat(source.fileno())
        size = stat.st_size
        if match and any(match.groups()) and size:
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start, end = max(0, size - int(right)), size - 1
            if 0 <= start <= end < size:
                source = path.open('rb')
                self._byte_range = (start, end)
                self.send_response(206)
                self.send_header('Content-Type', self.guess_type(str(path)))
                self.send_header('Content-Length', str(end - start + 1))
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.send_header('Last-Modified', self.date_time_string(stat.st_mtime))
                self.end_headers()
                return source
        self.send_response(416)
        self.send_header('Content-Range', f'bytes */{size}')
        self.send_header('Content-Length', '0')
        self.end_headers()
        return None

    def copyfile(self, source, outputfile):
        if self._byte_range is None:
            return super().copyfile(source, outputfile)
        start, end = self._byte_range
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            block = source.read(min(65536, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8771)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / 'docs/research'
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(root)))
    print(f'Serving {root} at http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

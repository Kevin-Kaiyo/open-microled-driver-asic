#!/usr/bin/env python3
"""Loopback-only public research preview; private build and environment paths denied."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[2]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def send_head(self):
  p=Path(self.translate_path(self.path)).resolve()
  try:rel=p.relative_to(ROOT)
  except ValueError:self.send_error(403);return None
  allowed=bool(rel.parts) and (rel.parts[0] in ['docs','evidence'] or rel.parts[:2]==('analog','models'))
  if not allowed:self.send_error(403,'Only public reports, evidence and model cards');return None
  return super().send_head()
 def list_directory(self,path):self.send_error(403,'Directory listing disabled');return None
 def end_headers(self):self.send_header('Cache-Control','no-store');super().end_headers()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8772);a=p.parse_args()
 print(f'Preview http://127.0.0.1:{a.port}/docs/research/microled-dynamic-validation-20261108/index.html',flush=True)
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()

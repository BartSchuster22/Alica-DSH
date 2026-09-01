#!/usr/bin/env python3
"""Acceptance-only S3-compatible object sink and alert webhook."""
import hashlib, json, os, pathlib, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=pathlib.Path(sys.argv[1]).resolve(); ROOT.mkdir(parents=True,exist_ok=True)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def safe_target(self):
        target=(ROOT/self.path.lstrip('/')).resolve()
        if ROOT not in target.parents: raise ValueError('unsafe path')
        return target
    def do_PUT(self):
        if not self.headers.get('Authorization','').startswith('AWS4-HMAC-SHA256 '): self.send_error(403); return
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        expected=self.headers.get('x-amz-content-sha256')
        if expected and expected!='UNSIGNED-PAYLOAD' and hashlib.sha256(body).hexdigest()!=expected: self.send_error(400); return
        target=self.safe_target();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body);os.chmod(target,0o600)
        self.send_response(200);self.end_headers()
    def do_GET(self):
        target=self.safe_target()
        if not target.is_file(): self.send_error(404);return
        body=target.read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if self.path!='/webhook': self.send_error(404);return
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        value=json.loads(body);assert value['schemaVersion']=='alica-operations-report/v1'
        target=ROOT/'webhook-deliveries.jsonl';target.open('ab').write(body+b'\n')
        self.send_response(204);self.end_headers()
ThreadingHTTPServer(('0.0.0.0',9000),Handler).serve_forever()

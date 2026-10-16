"""Loopback-only test preview; reuse the existing production-template renderer."""
import runpy
from pathlib import Path
from http.server import ThreadingHTTPServer

if __name__ == '__main__':
    fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'gui05' / 'preview.py'))
    ThreadingHTTPServer(('127.0.0.1', 8776), fixture['base'].Handler).serve_forever()

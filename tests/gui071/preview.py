"""Loopback fixture using actual dashboard capability projection and templates."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
import runpy
Handler = runpy.run_path(str(Path(__file__).resolve().parents[1]/'gui02/preview.py'))['Handler']
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8772),Handler).serve_forever()

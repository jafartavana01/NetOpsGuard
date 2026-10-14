"""Loopback actual-template preview; API responses are browser fixtures only."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
base.PAGES['/platform/device-credentials']='device_credentials.html'
base.PAGES['/security/schedule']='security_schedule.html'
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8773),base.Handler).serve_forever()

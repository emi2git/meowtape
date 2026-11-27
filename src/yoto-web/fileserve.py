"""Serve ~/Library/CloudStorage/SynologyDrive-SynologySync/mp3 on 127.0.0.1:8766 so the Yoto page can fetch files
(CORS + Private Network Access headers)."""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.environ.get("MP3_DIR") or os.path.expanduser("~/Library/CloudStorage/SynologyDrive-SynologySync/mp3")


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "https://my.yotoplay.com")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", 8766), H).serve_forever()

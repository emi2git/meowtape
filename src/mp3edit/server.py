#!/usr/bin/env python3
"""mp3 edit — a local, browser-based trimmer for the music folder.

Serves editor.html on 127.0.0.1, streams the audio (with Range support so the
browser can seek), hands back a waveform computed by ffmpeg, and saves edits
losslessly with stream copy. The original is never touched: results land next
to it as "<name> (edited).<ext>".

    server.py <music dir> [file]
"""
import array
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUDIO_EXT = (".mp3", ".m4a", ".m4b", ".flac", ".wav", ".aac", ".ogg")
MIME = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".m4b": "audio/mp4",
        ".flac": "audio/flac", ".wav": "audio/wav", ".aac": "audio/aac",
        ".ogg": "audio/ogg"}
HERE = os.path.dirname(os.path.abspath(__file__))
PEAK_RATE = 1000   # samples/s fed to the waveform — plenty for drawing
PEAK_BUCKETS = 4000

ROOT = ""


def safe_path(rel):
    """A path inside ROOT, or None — the page can't reach outside the folder."""
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    return p


def list_files():
    out = []
    for d, _, names in os.walk(ROOT):
        for n in names:
            if n.lower().endswith(AUDIO_EXT) and not n.startswith("."):
                full = os.path.join(d, n)
                out.append({"path": os.path.relpath(full, ROOT),
                            "mtime": os.path.getmtime(full)})
    out.sort(key=lambda f: -f["mtime"])
    return out


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def peaks(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1",
                          "-ar", str(PEAK_RATE), "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    n = len(a)
    if not n:
        return []
    step = max(1, n // PEAK_BUCKETS)
    return [round(max(max(a[i:i + step]), -min(a[i:i + step])) / 32768, 3)
            for i in range(0, n, step)]


def edited_name(src):
    base, ext = os.path.splitext(src)
    return f"{base} (edited){ext}"


def save(src, keep):
    """Write the kept [start, end] ranges of src, in order, to a new file."""
    out = edited_name(src)
    if os.path.realpath(out) == os.path.realpath(src):
        raise ValueError("would overwrite the original")
    ext = os.path.splitext(src)[1]
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (a, b) in enumerate(keep):
            part = os.path.join(tmp, f"{i}{ext}")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}",
                            "-to", f"{b:.3f}", "-i", src, "-map", "0",
                            "-c", "copy", "-map_metadata", "0", part],
                           check=True)
            parts.append(part)
        if len(parts) == 1:
            os.replace(parts[0], out)
        else:
            lst = os.path.join(tmp, "list.txt")
            with open(lst, "w") as f:
                for p in parts:
                    f.write("file '%s'\n" % p.replace("'", "'\\''"))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat",
                            "-safe", "0", "-i", lst, "-i", src,
                            "-map", "0", "-map_metadata", "1",
                            "-c", "copy", out], check=True)
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            with open(os.path.join(HERE, "editor.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/files":
            self.send_json({"root": ROOT, "files": list_files(),
                            "start": START})
        elif u.path == "/api/info":
            p = safe_path(q.get("f", [""])[0])
            if not p or not os.path.isfile(p):
                return self.send_json({"error": "no such file"}, 404)
            self.send_json({"duration": duration(p), "peaks": peaks(p)})
        elif u.path == "/audio":
            p = safe_path(q.get("f", [""])[0])
            if not p or not os.path.isfile(p):
                return self.send_error(404)
            self.stream(p)
        else:
            self.send_error(404)

    def stream(self, p):
        size = os.path.getsize(p)
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            if a:
                start = int(a)
                end = int(b) if b else end
            else:
                start = size - int(b)
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type",
                         MIME.get(os.path.splitext(p)[1].lower(), "audio/mpeg"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(p, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        if self.path != "/api/save":
            return self.send_error(404)
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        p = safe_path(req.get("f", ""))
        if not p or not os.path.isfile(p):
            return self.send_json({"error": "no such file"}, 404)
        keep = [(float(a), float(b)) for a, b in req.get("keep", []) if b > a]
        if not keep:
            return self.send_json({"error": "nothing left to keep"}, 400)
        try:
            out = save(p, keep)
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"out": os.path.relpath(out, ROOT),
                        "duration": duration(out)})


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


if __name__ == "__main__":
    ROOT = os.path.realpath(sys.argv[1])
    START = ""
    if len(sys.argv) > 2 and sys.argv[2]:
        f = os.path.realpath(sys.argv[2])
        if not f.startswith(ROOT + os.sep):   # a file outside the music folder
            ROOT = os.path.dirname(f)
        START = os.path.relpath(f, ROOT)
    port = int(os.environ.get("MP3EDIT_PORT") or free_port())
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"mp3 edit → {url}   (Ctrl-C to quit)", flush=True)
    if not os.environ.get("MP3EDIT_NO_OPEN"):
        threading.Timer(0.3, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()

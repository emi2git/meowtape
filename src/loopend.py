#!/usr/bin/env python3
"""loopend — where a looping recording starts over.

    loopend <capture.caf|.flac|.wav> [--min 30] [--print-onset]

Prints the time, in seconds into the file, at which the audio begins repeating
its own opening — or nothing if it hasn't yet. Safe to run on a .caf that
blackrec is still writing.

For players that repeat one track forever and can't say how long it is: the
opening's loudness contour (15 s of it, 10 ms steps) is slid along the rest of
the recording, and the first place it matches almost exactly is the restart.
Loudness, not samples, so a restart that lands a few milliseconds off, or
through a resampler, still matches.
"""

import struct
import subprocess
import sys

import numpy as np

RATE = 48000
HOP = 480            # 10 ms
PRINT_LEN = 1500     # 15 s of contour
FLOOR_DB = -45.0
MATCH = 0.97


def read_caf(path):
    """float32 samples from a CAF — including one still being written, whose
    data chunk size is still -1."""
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != b"caff":
        return None
    pos, rate, ch, flags, bits = 8, RATE, 2, 1, 32
    while pos + 12 <= len(buf):
        kind = buf[pos:pos + 4]
        size = struct.unpack(">q", buf[pos + 4:pos + 12])[0]
        body = pos + 12
        if kind == b"desc":
            rate, fmt, flags, _bpp, _fpp, ch, bits = struct.unpack(">d4sIIIII", buf[body:body + 32])
        elif kind == b"data":
            end = len(buf) if size < 0 else min(len(buf), body + size)
            data = buf[body + 4:end]                       # 4 bytes: edit count
            little = bool(flags & 2)
            if flags & 1 and bits == 32:
                dt = "<f4" if little else ">f4"
            elif bits == 16:
                dt = "<i2" if little else ">i2"
            else:
                dt = "<i4" if little else ">i4"
            n = len(data) // (np.dtype(dt).itemsize * ch) * ch
            x = np.frombuffer(data[:n * np.dtype(dt).itemsize], dtype=dt).astype(np.float32)
            if not flags & 1:
                x /= float(2 ** (bits - 1))
            return x.reshape(-1, ch).mean(axis=1), int(rate)
        pos = body + size
    return None


def read_any(path):
    if path.endswith(".caf"):
        got = read_caf(path)
        if got:
            return got
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4"), RATE


def contour(x, rate):
    hop = rate // 100
    n = len(x) // hop
    frames = x[:n * hop].reshape(n, hop)
    return 10 * np.log10(np.mean(frames ** 2, axis=1) + 1e-10)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    path = args[0]
    min_gap = float(args[args.index("--min") + 1]) if "--min" in args else 30.0

    x, rate = read_any(path)
    env = contour(x, rate)
    loud = np.nonzero(env > FLOOR_DB)[0]
    if not len(loud):
        return
    onset = int(loud[0])
    if "--print-onset" in args:
        print(f"onset {onset / 100:.2f}")

    tpl = np.maximum(env[onset:onset + PRINT_LEN], FLOOR_DB - 20)
    start = onset + int(min_gap * 100)
    if len(tpl) < PRINT_LEN or len(env) < start + PRINT_LEN:
        return
    tpl = (tpl - tpl.mean()) / (tpl.std() + 1e-9)
    hay = np.maximum(env[start:], FLOOR_DB - 20)

    # normalised cross-correlation over every offset
    m = len(tpl)
    csum = np.concatenate(([0.0], np.cumsum(hay)))
    csum2 = np.concatenate(([0.0], np.cumsum(hay ** 2)))
    win_mean = (csum[m:] - csum[:-m]) / m
    win_std = np.sqrt(np.maximum((csum2[m:] - csum2[:-m]) / m - win_mean ** 2, 1e-12))
    dots = np.correlate(hay, tpl, mode="valid")
    ncc = dots / (m * win_std)

    hits = np.nonzero(ncc > MATCH)[0]
    if not len(hits):
        return
    # the best match in the first run of hits
    run_end = hits[0]
    while run_end + 1 < len(ncc) and ncc[run_end + 1] > MATCH:
        run_end += 1
    best = hits[0] + int(np.argmax(ncc[hits[0]:run_end + 1]))
    print(f"{(start + best) / 100:.2f}")


if __name__ == "__main__":
    main()

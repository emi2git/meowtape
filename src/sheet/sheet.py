#!/usr/bin/env python3
"""mp3 sheet — a YouTube link (or an audio file) → a lead sheet: melody + chords.

    sheet.py <url | file> [--out DIR] [--no-lyrics] [--key C] [--meter 3|4]

Stages (each cached in <out>/<title>/.work, so a rerun only redoes what changed):
  1 fetch    yt-dlp → wav, title/artist, captions if any
  2 split    demucs htdemucs → vocals / accompaniment
  3 grid     beats on the accompaniment; meter (3 or 4) and where bar 1 falls
  4 key      Krumhansl–Schmuckler on the accompaniment's pitch classes
  5 chords   half-bar chroma + bass → Viterbi over maj/min/7 with a key prior
  6 melody   basic-pitch on the vocal stem → one line, octaves fixed, in key,
             quantised to eighths
  7 lyrics   caption words laid one per note inside each caption line
  8 engrave  LilyPond → PDF + MIDI

Automatic transcription: expect the right key, a usable chord chart and a
melody that's close but needs a musician's pass — rhythms especially.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
YTDLP = Path.home() / "venv/bin/yt-dlp"
PY = Path(sys.executable)
SR = 22050
HOP = 512
NOTE = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def log(*a):
    print("·", *a, flush=True)


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd[:3]))}…\n{r.stderr[-1500:]}")
    return r


def slug(s):
    s = re.sub(r"\s*[\[(（【].*?[\])）】]", "", s)          # [id], (Official MV)…
    s = re.sub(r"[\\/:*?\"<>|｜]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:80] or "sheet"


# ── 1 fetch ─────────────────────────────────────────────────────────────────
def fetch(src, out_root):
    if Path(src).exists():
        p = Path(src).resolve()
        t, _, a = slug(p.stem).partition(" - ")
        meta = {"title": t or slug(p.stem), "artist": a, "id": p.stem}
        work = out_root / meta["title"] / ".work"
        work.mkdir(parents=True, exist_ok=True)
        if not (work / "audio.wav").exists():
            run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "2", "-ar", "44100", work / "audio.wav"])
        return meta, work
    info = json.loads(run([YTDLP, "-J", "--no-playlist", src]).stdout)
    title = info.get("track") or info.get("title") or info["id"]
    artist = info.get("artist") or info.get("creator") or ""
    if not artist and " - " in info.get("title", ""):
        a, b = [slug(x) for x in info["title"].split(" - ", 1)]
        chan = (info.get("channel") or info.get("uploader") or "").lower()
        # "Artist - Song" is the English habit, "Song - Artist" the Vietnamese one;
        # the channel name settles it when it matches either side
        if a.lower() in chan or re.search(r"[À-ỹ]", a + b) is None:
            artist, title = a, b
        else:
            title, artist = a, b
        if b.lower() in chan:
            title, artist = a, b
    meta = {"title": slug(title), "artist": slug(artist), "id": info["id"],
            "url": info.get("webpage_url", src)}
    work = out_root / meta["title"] / ".work"
    work.mkdir(parents=True, exist_ok=True)
    if not (work / "audio.wav").exists():
        log("downloading", meta["title"])
        run([YTDLP, "-q", "--no-playlist", "-x", "--audio-format", "wav",
             "-o", str(work / "audio.%(ext)s"), meta["url"]])
    if not list(work.glob("subs*.json3")) and not list(work.glob("subs*.vtt")):
        subprocess.run([str(YTDLP), "-q", "--no-playlist", "--skip-download",
                        "--write-subs", "--write-auto-subs", "--sub-format", "json3/vtt/best",
                        "--sub-langs", "vi,vi-orig,en,en-orig,zh-Hans,zh-Hant",
                        "-o", str(work / "subs.%(ext)s"), meta["url"]],
                       capture_output=True)
    json.dump(meta, open(work / "meta.json", "w"), ensure_ascii=False)
    return meta, work


# ── 2 split ─────────────────────────────────────────────────────────────────
def split(work):
    d = work / "stems/htdemucs/audio"
    if (d / "vocals.wav").exists():
        return d / "vocals.wav", d / "no_vocals.wav"
    log("separating vocals (demucs, ~1–2 min)")
    for dev in ("mps", "cpu"):
        r = subprocess.run([PY, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs",
                            "-d", dev, "-o", work / "stems", work / "audio.wav"],
                           capture_output=True, text=True)
        if r.returncode == 0 and (d / "vocals.wav").exists():
            break
    else:
        sys.exit("demucs failed:\n" + r.stderr[-1500:])
    return d / "vocals.wav", d / "no_vocals.wav"


# ── 3 grid ──────────────────────────────────────────────────────────────────
def grid(acc_path, force_meter=None):
    import librosa
    y, _ = librosa.load(acc_path, sr=SR, mono=True)
    dur = len(y) / SR
    oe = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oe, sr=SR, hop_length=HOP, trim=False)
    bt = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)
    period = float(np.median(np.diff(bt)))
    # keep the beat a singable pulse: 60–150 bpm
    if 60 / period > 150:
        bt, period = bt[::2], period * 2
    elif 60 / period < 60:
        bt = np.sort(np.concatenate([bt, bt[:-1] + np.diff(bt) / 2])); period /= 2
    # extend the grid to cover the whole song
    pre = np.arange(bt[0] - period, 0, -period)[::-1]
    post = np.arange(bt[-1] + period, dur + period, period)
    bt = np.concatenate([pre, bt, post])

    yh = librosa.effects.harmonic(y, margin=3)
    fr = librosa.time_to_frames(bt, sr=SR, hop_length=HOP)
    ch = librosa.feature.chroma_cqt(y=yh, sr=SR, hop_length=HOP, bins_per_octave=36, norm=None)
    bass = librosa.feature.chroma_cqt(y=yh, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C1"),
                                      n_octaves=3, bins_per_octave=36, norm=None)
    ch = librosa.util.sync(ch, fr, aggregate=np.median, pad=False)
    bass = librosa.util.sync(bass, fr, aggregate=np.median, pad=False)
    n = min(len(bt) - 1, ch.shape[1])
    ch, bass = ch[:, :n], bass[:, :n]
    acc = librosa.util.sync(oe[None, :], fr, aggregate=np.max, pad=False)[0][:n]

    # meter + downbeat: chords change and the band leans on bar lines
    unit = ch / (np.linalg.norm(ch, axis=0, keepdims=True) + 1e-9)
    nov = np.r_[0, 1 - (unit[:, 1:] * unit[:, :-1]).sum(0)]
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    s = z(nov) + 0.5 * z(acc)
    best = {}
    for m in (3, 4):
        sc = [s[o::m].mean() for o in range(m)]
        best[m] = (max(sc), int(np.argmax(sc)))
    meter = force_meter or (3 if best[3][0] > best[4][0] * 1.25 + 0.05 else 4)
    off = best[meter][1]
    log(f"tempo ≈ {60 / period:.0f} bpm, {meter}/4, bar 1 at beat {off}")
    return dict(beats=bt[:n + 1].tolist(), chroma=ch.tolist(), bass=bass.tolist(),
                meter=meter, off=off, bpm=60 / period, dur=dur)


# ── 4 key ───────────────────────────────────────────────────────────────────
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def key_of(ch, forced=None):
    if forced:
        f = forced.replace("m", "")
        root = (SHARP.index(f) if f in SHARP else NOTE.index(f))
        return root, forced.endswith("m")
    v = np.asarray(ch).sum(1)
    sc = [(np.corrcoef(v, np.roll(MAJ, i))[0, 1], i, False) for i in range(12)] + \
         [(np.corrcoef(v, np.roll(MIN, i))[0, 1], i, True) for i in range(12)]
    sc.sort(reverse=True)
    return sc[0][1], sc[0][2]


def sharp_key(root, minor):
    """Keys written with sharps: G D A E B F# (major), Em Bm F#m C#m G#m (minor)."""
    return (root in (7, 2, 9, 4, 11, 6) and not minor) or (minor and root in (4, 11, 6, 1, 8))


def key_name(root, minor):
    return (SHARP if sharp_key(root, minor) else NOTE)[root] + ("m" if minor else "")


# ── 5 chords ────────────────────────────────────────────────────────────────
QUAL = {"": ([0, 4, 7], 0.0), "m": ([0, 3, 7], 0.0), "7": ([0, 4, 7, 10], 0.05)}


def chords(g, root, minor):
    ch = np.asarray(g["chroma"]); bass = np.asarray(g["bass"])
    m, off = g["meter"], g["off"]
    step = 2 if m == 4 else 3                        # a chord per half bar (4/4) or bar (3/4)
    starts = list(range(off % step, ch.shape[1], step))
    if off % step:
        starts = [0] + starts
    seg = np.stack([ch[:, a:b].sum(1) for a, b in zip(starts, starts[1:] + [ch.shape[1]])], 1)
    sbass = np.stack([bass[:, a:b].sum(1) for a, b in zip(starts, starts[1:] + [ch.shape[1]])], 1)
    energy = seg.sum(0)
    seg = seg / (np.linalg.norm(seg, axis=0, keepdims=True) + 1e-9)
    sbass = sbass / (sbass.max(0, keepdims=True) + 1e-9)

    scale = [0, 2, 3, 5, 7, 8, 10] if minor else [0, 2, 4, 5, 7, 9, 11]
    diat = set()
    for i, d in enumerate(scale):
        third = (scale[(i + 2) % 7] - d) % 12
        diat.add(((root + d) % 12, "" if third == 4 else "m"))
    diat.add(((root + 7) % 12, "7")); diat.add(((root + 7) % 12, ""))   # V / V7 in minor too
    names, M, prior = [], [], []
    for r in range(12):
        for q, (iv, pen) in QUAL.items():
            t = np.zeros(12)
            for k, i in enumerate(iv):
                t[(r + i) % 12] = [1.0, 0.8, 0.9, 0.6][k]
            names.append((r, q)); M.append(t / np.linalg.norm(t))
            prior.append((0.10 if (r, q) in diat else -0.07 if q == "m" else -0.02) - pen)   # borrowed majors/7ths are common, stray minors aren't
    M, prior = np.array(M), np.array(prior)
    E = M @ seg + prior[:, None] + 0.12 * np.array([sbass[r] for r, _ in names])
    # Viterbi: changing chord costs a little, so chords hold across bars
    K, T = E.shape; SW = 0.10
    dp = E[:, 0].copy(); bp = np.zeros((K, T), int)
    for t in range(1, T):
        j = int(dp.argmax())
        stay, move = dp, dp[j] - SW
        bp[:, t] = np.where(stay >= move, np.arange(K), j)
        dp = np.maximum(stay, move) + E[:, t]
    path = [int(dp.argmax())]
    for t in range(T - 1, 0, -1):
        path.append(bp[path[-1], t])
    path = path[::-1]
    quiet = energy < 0.08 * np.median(energy)
    out = []
    for i, (a, k) in enumerate(zip(starts, path)):
        out.append([a, None if quiet[i] else names[k]])
    return out, step


# ── 6 melody ────────────────────────────────────────────────────────────────
def melody(vocals, work, g, root, minor):
    cache = work / "notes.json"
    if cache.exists():
        raw = json.load(open(cache))
    else:
        log("transcribing the vocal line (basic-pitch)")
        import logging; logging.disable(logging.WARNING)
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
        _, _, ev = predict(str(vocals), ICASSP_2022_MODEL_PATH, onset_threshold=0.5,
                           frame_threshold=0.3, minimum_note_length=90,
                           minimum_frequency=75, maximum_frequency=1100)
        raw = sorted([[float(s), float(e), int(p), float(a)] for s, e, p, a, *_ in ev])
        json.dump(raw, open(cache, "w"))
    # one line: at an overlap keep the stronger, longer note
    mono = []
    for s, e, p, a in raw:
        if e - s < 0.09:
            continue
        if mono and s < mono[-1][1] - 0.04:
            ps, pe, pp, pa = mono[-1]
            if (e - s) * a > (pe - ps) * pa:
                mono[-1] = [s, e, p, a]
            continue
        mono.append([s, e, p, a])
    if not mono:
        return []
    # instruments leaking into the vocal stem come out quiet: drop those notes
    import librosa
    yv, _ = librosa.load(vocals, sr=SR, mono=True)
    rms = librosa.feature.rms(y=yv, hop_length=HOP)[0]
    span = lambda a, b: rms[int(a * SR / HOP):max(int(a * SR / HOP) + 1, int(b * SR / HOP))]
    level = np.array([span(s, e).mean() for s, e, *_ in mono])
    mono = [n for n, l in zip(mono, level) if l > 0.3 * np.median(level)]
    floor = 0.25 * np.median(level)
    def voiced(a, b):
        seg = span(a, b)
        return float((seg > floor).mean()) if len(seg) else 0.0
    p = np.array([n[2] for n in mono], float)
    for _ in range(3):                                    # octave slips
        med = np.array([np.median(p[max(0, i - 8):i + 9]) for i in range(len(p))])
        p = np.where(p - med > 7, p - 12, np.where(p - med < -7, p + 12, p))
    gm = np.median(p)                                     # nothing an octave+ off the singer's range
    p = np.where(p - gm > 12, p - 12, np.where(p - gm < -12, p + 12, p))
    p += 12 * round((67 - np.median(p)) / 12)             # sit it on the treble staff
    scale = {(root + d) % 12 for d in ([0, 2, 3, 5, 7, 8, 10, 11] if minor else [0, 2, 4, 5, 7, 9, 11])}
    hist = np.bincount(p.astype(int) % 12, minlength=12) / len(p)
    keep = scale | {pc for pc in range(12) if hist[pc] > 0.05}   # accidentals the song really uses
    def snap(x):
        if int(x) % 12 in keep:
            return int(x)
        return min((int(x) + d for d in (-1, 1) if (int(x) + d) % 12 in keep), key=lambda v: abs(v - x))
    p = [snap(x) for x in p]

    # quantise to eighths on the beat grid
    bt = np.asarray(g["beats"]); idx = np.arange(len(bt))
    pos = lambda t: float(np.interp(t, bt, idx, left=(t - bt[0]) / (bt[1] - bt[0]),
                                    right=len(bt) - 1 + (t - bt[-1]) / (bt[-1] - bt[-2]))) * 2
    notes = {}
    for (s, e, _, a), pitch in zip(mono, p):
        qs, qe = round(pos(s)), round(pos(e))
        if qs < 0:
            continue
        d = max(1, qe - qs)
        if qs not in notes or d > notes[qs][0]:
            notes[qs] = [d, pitch, s, e]
    qs = sorted(notes)
    out = []
    for i, k in enumerate(qs):
        d, pitch, s, e = notes[k]
        nxt = qs[i + 1] if i + 1 < len(qs) else k + d
        d = min(d, nxt - k)
        if i + 1 < len(qs) and nxt > k + d:
            gap_s, gap_e = e, notes[qs[i + 1]][2]
            # hold the note through the gap while the voice is still sounding —
            # basic-pitch ends notes early; a rest should mean the singer stopped
            if gap_e - gap_s < 0.18 or voiced(gap_s, gap_e) > 0.6:
                d = nxt - k
        out.append([k, d, pitch, s])
    log(f"melody: {len(out)} notes")
    return out


# ── 7 lyrics ────────────────────────────────────────────────────────────────
def lyrics(work, notes):
    # prefer hand-made captions over auto ones, Vietnamese first
    files = sorted(list(work.glob("subs*.json3")) + list(work.glob("subs*.vtt")),
                   key=lambda f: ("orig" in f.name, not f.name.startswith("subs.vi"), f.name))
    if not files or not notes:
        return None
    cues = []
    if files[0].suffix == ".json3":
        for ev in json.load(open(files[0])).get("events", []):
            txt = "".join(s.get("utf8", "") for s in ev.get("segs", []))
            t0 = ev["tStartMs"] / 1000
            cues.append((t0, t0 + ev.get("dDurationMs", 2000) / 1000, txt))
    else:
        ts = lambda h: sum(float(x) * 60 ** i for i, x in enumerate(reversed(h.replace(",", ".").split(":"))))
        for block in re.split(r"\n\s*\n", files[0].read_text()):
            m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)[^\n]*\n(.*)", block, re.S)
            if m:
                cues.append((ts(m[1]), ts(m[2]), re.sub(r"<[^>]+>", "", m[3])))
    lines = []
    for t0, t1, txt in cues:
        txt = txt.strip()
        if not txt or re.fullmatch(r"[\[(（].*[\])）]|[♪\s]+", txt):
            continue
        words = re.findall(r"[\w'’-]+", txt)
        if words:
            lines.append((t0, t1, words))
    if not lines:
        return None
    syl = ["_"] * len(notes)
    starts = [n[3] for n in notes]
    for t0, t1, words in lines:
        idx = [i for i, s in enumerate(starts) if t0 - 0.25 <= s < t1 + 0.1 and syl[i] == "_"]
        if not idx:
            continue
        if len(words) > len(idx):
            words = words[:len(idx) - 1] + [" ".join(words[len(idx) - 1:])]
        for i, w in zip(idx, words):
            syl[i] = w
    if sum(s != "_" for s in syl) < 0.2 * len(notes):
        return None
    log(f"lyrics: {sum(s != '_' for s in syl)} syllables from captions ({files[0].name})")
    return syl


# ── 8 engrave ───────────────────────────────────────────────────────────────
LY_SHARP = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]
LY_FLAT = ["c", "des", "d", "ees", "e", "f", "ges", "g", "aes", "a", "bes", "b"]


def engrave(meta, g, root, minor, chs, step, notes, syl, outdir):
    m, off = g["meter"], g["off"]
    B = 2 * m                                     # eighths per bar
    names = LY_SHARP if sharp_key(root, minor) else LY_FLAT
    pitch = lambda p: names[p % 12] + ("'" * (p // 12 - 4) if p >= 48 else "," * (4 - p // 12))

    first_bar = max(0, (notes[0][0] - 2 * off) // B) if notes else 0
    last = max(k + d for k, d, *_ in notes) if notes else 0
    last_bar = (last - 2 * off) // B + 1
    start8 = 2 * off + first_bar * B              # grid eighth where the sheet begins

    def pieces(pos, length):
        out = []
        while length > 0:
            p = pos % B
            for d in (8, 6, 4, 3, 2, 1):
                ok = d <= length and d <= B - p and (
                    d == 1 or (d == 2 and p % 2 == 0) or (d == 3 and p % 2 == 0) or
                    (d == 4 and p % 4 == 0 and (m == 4 or p == 0)) or (d in (6, 8) and p == 0))
                if ok:
                    out.append(d); pos += d; length -= d; break
        return out
    DUR = {1: "8", 2: "4", 3: "4.", 4: "2", 6: "2.", 8: "1"}

    mel, pos = [], start8
    for k, d, p, _ in notes:
        if k < start8:
            continue
        if k > pos:
            mel += ["r" + DUR[x] for x in pieces(pos, k - pos)]
        ps = pieces(k, d)
        mel += [pitch(p) + DUR[x] + ("~" if i < len(ps) - 1 else "") for i, x in enumerate(ps)]
        pos = k + d
    end8 = start8 + (last_bar - first_bar) * B
    if end8 > pos:
        mel += ["r" + DUR[x] for x in pieces(pos, end8 - pos)]

    crd = []
    beat0 = start8 // 2
    segs = [(a, c) for a, c in chs]
    for i, (a, c) in enumerate(segs):
        b = segs[i + 1][0] if i + 1 < len(segs) else a + step
        a2, b2 = max(a, beat0), min(b, beat0 + (last_bar - first_bar) * m)
        if b2 <= a2:
            continue
        for x in pieces(2 * a2, 2 * (b2 - a2)):
            if c is None:
                crd.append("s" + DUR[x])
            else:
                r, q = c
                crd.append(names[r] + DUR[x] + {"": "", "m": ":m", "7": ":7"}[q])

    lyr = ""
    if syl:
        kept = [s for (k, *_), s in zip(notes, syl) if k >= start8]
        esc = lambda w: w if w == "_" else '"' + w.replace('"', "'") + '"'
        lyr = "\n    \\addlyrics { " + " ".join(esc(w) for w in kept) + " }"

    kn = key_name(root, minor)
    tonic = names[root]
    title = meta["title"].replace('"', "'")
    src = f'''\\version "2.24.0"
\\header {{
  title = "{title}"
  composer = "{meta.get('artist', '').replace('"', "'")}"
  subtitle = "lead sheet · key {kn} · auto-transcribed"
  tagline = ##f
}}
\\paper {{ indent = 0 ragged-last-bottom = ##t
  #(set-paper-size "a4") }}
chordNames = \\chordmode {{ \\set chordChanges = ##t {" ".join(crd)} }}
melody = {{ \\clef treble \\key {tonic} \\{"minor" if minor else "major"} \\time {m}/4
  \\tempo 4 = {round(g["bpm"])}
  {" ".join(mel)} \\bar "|."
}}
\\score {{
  << \\new ChordNames {{ \\chordNames }}
     \\new Staff \\with {{ \\consists "Completion_heads_engraver" }} {{ \\melody }}{lyr} >>
  \\layout {{ \\context {{ \\Score \\override BarNumber.break-visibility = ##(#f #t #t) }} }}
  \\midi {{ }}
}}
'''
    outdir.mkdir(parents=True, exist_ok=True)
    stem = outdir / meta["title"]
    (outdir / (meta["title"] + ".ly")).write_text(src)
    r = subprocess.run(["lilypond", "-s", "-o", str(stem), str(stem) + ".ly"], capture_output=True, text=True)
    if r.returncode:
        sys.exit("lilypond failed:\n" + r.stderr[-2000:])
    return stem.with_suffix(".pdf")


def main():
    ap = argparse.ArgumentParser(description="YouTube link or audio file → lead sheet (melody + chords)")
    ap.add_argument("src")
    ap.add_argument("--out", default=str(Path.home() / "Downloads/sheets"))
    ap.add_argument("--no-lyrics", action="store_true")
    ap.add_argument("--key", help="force the key, e.g. G or Em")
    ap.add_argument("--meter", type=int, choices=(3, 4), help="force 3/4 or 4/4")
    a = ap.parse_args()

    meta, work = fetch(a.src, Path(a.out).expanduser())
    vocals, acc = split(work)
    gcache = work / "grid.json"
    if gcache.exists() and not a.meter:
        g = json.load(open(gcache))
    else:
        g = grid(acc, a.meter); json.dump(g, open(gcache, "w"))
    root, minor = key_of(g["chroma"], a.key)
    log("key", key_name(root, minor))
    chs, step = chords(g, root, minor)
    notes = melody(vocals, work, g, root, minor)
    syl = None if a.no_lyrics else lyrics(work, notes)
    pdf = engrave(meta, g, root, minor, chs, step, notes, syl, work.parent)
    spell = SHARP if sharp_key(root, minor) else NOTE
    used = list(dict.fromkeys(spell[c[0]] + c[1] for _, c in chs if c))
    log("chords:", " ".join(used))
    print(pdf)
    if not os.environ.get("SHEET_NO_OPEN"):
        subprocess.run(["open", str(pdf)])


if __name__ == "__main__":
    main()

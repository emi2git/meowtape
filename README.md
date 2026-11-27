# Emi MP3

Small macOS tools that get music and audiobooks onto kids' devices: record
songs from Spotify and episodes from Ximalaya **silently**, download, trim and
check tracks, then turn each folder into a **Yoto card** (tracks, cover and
pixel icon) or copy it to an iPad or phone.

Why: a Yoto player and offline devices need plain audio files, sorted the way
a card plays. Doing that by hand, one song at a time, while the Mac blares the
music out loud, doesn't scale.

## The rules it keeps

- **Recording is silent.** Sound is routed to [BlackHole](https://github.com/ExistentialAudio/BlackHole)
  and captured there; nothing comes out of the speakers. The normal output
  device comes back by itself when the job is done (or with `mp3 speakers`).
- **One card folder = one Yoto card.** The music folder is always exactly
  two levels deep:

```
mp3/                          MP3_DIR (default: SynologyDrive …/mp3)
├── Music/                    super folder: no loose audio here
│   ├── <Card name>/          card folder → one Yoto card
│   │   ├── 01 Title - Artist.mp3
│   │   └── 02 Title - Artist.mp3
│   └── <Another card>/
├── Audiobooks/
│   └── <Book>/
│       └── 01 Chapter.mp3
└── .yoto-art/<Card name>/    icon.png (16×16), cover.png, preview.png
```

Card folder names must make sense on their own ("Vietnamese 2000s", not
"2000s"). Never nest a third level.

## Requirements

- macOS (CoreAudio, AppleScript)
- `brew install ffmpeg` (ffmpeg + ffprobe)
- `brew install blackhole-2ch` — the silent capture device
- Xcode command line tools (`swiftc`) for the native helpers
- Spotify desktop app for `mp3 song/songs/album/playlist`
- yt-dlp at `~/venv/bin/yt-dlp` for `mp3 get` and `mp3 sheet`
- 喜马拉雅 app for `mp3 mala` (plus Accessibility permission for the media keys)
- Google Chrome with a my.yotoplay.com tab for the `yoto-*` upload tools
- optional: a Python with demucs + basic-pitch + librosa for `mp3 sheet`
  (point `MP3_SHEET_PY` at it)

## Install

```sh
git clone https://github.com/emi2git/emi-mp3 ~/git/apps/emi-mp3
~/git/apps/emi-mp3/build.sh          # swiftc → bin/blackrec, bin/audiodev, bin/mediakey; .venv for Python
export PATH="$HOME/git/apps/emi-mp3/bin:$PATH"
```

`mp3` with no arguments jumps to the music folder only through a shell
wrapper (a script can't `cd` your shell):

```zsh
mp3() { [[ $# -eq 0 ]] && cd "$(command mp3 dir)" || command mp3 "$@" }
alias mp3='noglob mp3'
```

Set `MP3_DIR` to work on another folder (handy for trying things out).

## Usage

### mp3 — record, download, tidy up

```sh
mp3 help                     # overview; mp3 help <command> for details
mp3 song  "https://open.spotify.com/track/<id>"      # one song → "05 Title - Artist.mp3", tagged
mp3 songs                    # paste link after link; q to finish
mp3 album "https://open.spotify.com/album/<id>"      # every song, skips ones you have
mp3 playlist "https://open.spotify.com/playlist/<id>"
mp3 mala  "https://xima.tv/<code>"                   # every Ximalaya episode, via its app
mp3 rec --silent [name]      # whatever the Mac plays, Return to stop
mp3 get   "<youtube url>"    # download best audio as mp3
mp3 check [file|dir]         # ★ quality rating (320 kbps / lossless = 5 stars)
mp3 cut   <file> 12          # lossless split into 12 equal parts
mp3 trimtop <file> 0:12      # lossless copy that starts 12 s in
mp3 edit  [file]             # browser editor: mark, keep/cut, save "(edited)" copy
mp3 sheet <url|file>         # lead sheet PDF: melody + chords (LilyPond)
mp3 speakers                 # put the sound back if a recording left it off
mp3 dir                      # print MP3_DIR
```

Spotify recordings run in real time and are trimmed to the track's exact
length. Turn crossfade off in Spotify. `--flac` / `--wav` give lossless files.

### Yoto cards

```sh
yoto-card-art [out]                  # 16×16 icon + cover per song card → $MP3_DIR/.yoto-art
yoto-xiaoyang-icons [out] [n]        # numbered lamb icons for the 小羊上山 cards
yoto-xiaoyang-stickers [folder]      # printable card stickers from box-set photos
yoto-serve                           # serve MP3_DIR on 127.0.0.1:8766 for the Yoto page
yoto-card "<Card name>"              # make a Yoto playlist from Music/<Card name> with art
yoto-addto <card code> "<Card name>" <file>…   # add tracks to an existing card
```

`yoto-card` / `yoto-addto` drive your own logged-in my.yotoplay.com tab in
Chrome (View ▸ Developer ▸ Allow JavaScript from Apple Events). Put that tab's
id in `src/yoto-web/tabid` (git-ignored).

### Low-level helpers

```sh
audiodev get | set <uid> | name <uid> | ensure-multi <speaker-uid>   # CoreAudio output device
blackrec [-d seconds] [-q] out.caf [device-uid]   # glitch-free capture from BlackHole
mediakey play|next|prev|fast|rewind|check         # send media keys (for apps without AppleScript)
spotify-tracks                                    # TSV of Spotify's current queue
loopend capture.caf [--min 30]                    # where a looping recording starts over
```

## Project layout

```
bin/            entry points (mp3, yoto-*, spotify-tracks, loopend) + built Swift tools
src/            blackrec.swift, audiodev.swift, mediakey.swift, loopend.py, yoto_*.py
src/mp3edit/    the `mp3 edit` browser editor (server.py + editor.html)
src/sheet/      the `mp3 sheet` pipeline
src/yoto-web/   my.yotoplay.com automation (card.sh, addto.sh, page scripts)
build.sh        compile the Swift tools, set up .venv
```

No audio, art, song lists or library data belong in this repo; `.gitignore`
keeps audio and images out.

Private: it records from Spotify, which Spotify's terms don't allow for
redistribution. For personal, offline listening only.

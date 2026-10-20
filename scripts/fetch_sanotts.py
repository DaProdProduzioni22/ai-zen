#!/usr/bin/env python3
"""Download the SanoTTS runtime and the Italian voices into the repo.

The site hosts them itself: no CDN, no third-party request at runtime, and the
whole thing keeps working offline once cached.

Source: https://github.com/Ampixa/sanoTTS (GPL-3.0)
"""
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(REPO, "sanotts")
BASE = "https://raw.githubusercontent.com/Ampixa/sanoTTS/master/web"

# The runtime: espeak-ng (G2P) plus the neural synthesis modules.
RUNTIME = [
    "snt_g2p.js", "snt_g2p.wasm", "snt_g2p.data",
    "snt_voice.js", "snt_voice.wasm",
    "snt_tts.js", "snt_tts.wasm",
]

# The voices we ship: the two Italian ones. The blog is in Italian, so these
# are the ones that matter. The English voices of the upstream project use a
# different runtime (the "nano" stack) and are not needed here.
VOICES = ["italian", "italian-tiny"]
VOICE_FILES = ["meta.json", "front_f16.bin", "dec_f16.bin"]


def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return False
    print("  downloading", url.rsplit("/", 1)[-1], "->", os.path.relpath(dest, REPO))
    req = urllib.request.Request(url, headers={"User-Agent": "ai-zen-build"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return True


def main():
    total = 0
    for f in RUNTIME:
        fetch("%s/%s" % (BASE, f), os.path.join(DEST, f))
    for v in VOICES:
        for f in VOICE_FILES:
            fetch("%s/voices/%s/%s" % (BASE, v, f), os.path.join(DEST, "voices", v, f))

    for root, _, files in os.walk(DEST):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    print("\n%s: %.1f MB" % (os.path.relpath(DEST, REPO), total / 1024 / 1024))
    print("licence: GPL-3.0 (sanoTTS) — see sanotts/LICENSE.txt")

    lic = """SanoTTS — in-browser neural text-to-speech
===========================================

Files in this directory come from https://github.com/Ampixa/sanoTTS
(branch master, web/ folder), licensed GPL-3.0-or-later.

  snt_g2p.js / snt_g2p.wasm / snt_g2p.data   espeak-ng phonemizer (WASM)
  snt_voice.js / snt_voice.wasm               voice weight loader
  snt_tts.js / snt_tts.wasm                   neural synthesis runtime
  voices/<key>/                               voice weights (front + decoder + meta)

espeak-ng is itself GPL-3.0. The phoneme data it ships is covered by the same
licence. See https://github.com/Ampixa/sanoTTS for the full text and for the
model weights' terms.

Why these files are committed: the site must work with no third-party
requests at runtime, and must keep working when the network goes away.
"""
    with open(os.path.join(DEST, "LICENSE.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(lic)
    return 0


if __name__ == "__main__":
    sys.exit(main())

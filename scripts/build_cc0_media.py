"""Compose extra scary sounds from CC0 OpenGameArt packs (build machine only: numpy + soundfile).

Usage: python build_cc0_media.py HITS_DIR CREATURE_DIR GHOST_FLAC AMBIENT_WAV
  HITS_DIR      extracted "Horror Hit Soundpack 1" (psychhead_, CC0)
  CREATURE_DIR  extracted "80 CC0 creature SFX" (rubberduck, CC0)
  GHOST_FLAC    "Ghost breath" ghostbreath.flac (qubodup, CC0)
  AMBIENT_WAV   "Ambient horror" ambient_horror.wav (techiew, CC0)
See custom_components/haunted_house/media/CREDITS.md.
"""
from pathlib import Path
import sys
import wave
import numpy as np
import soundfile as sf
from generate_horror_audio import SR, bandpass, drive, reverb

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "haunted_house" / "media"


def load(path, speed=1.0):
    x, rate = sf.read(str(path), always_2d=True)
    x = x.mean(axis=1)
    n = int(len(x) / rate * SR / speed)
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return x - np.mean(x)


def trim(x, threshold=.01):
    loud = np.where(np.abs(x) > threshold * np.max(np.abs(x)))[0]
    return x[loud[0]: loud[-1] + 1] if len(loud) else x


def norm(x, level=.93):
    return x / max(1e-9, np.max(np.abs(x))) * level


def mix(*layers):
    size = max(len(x) + int(at * SR) for x, at, _ in layers)
    out = np.zeros(size)
    for x, at, gain in layers:
        out[int(at * SR): int(at * SR) + len(x)] += norm(x) * gain
    return out


def write(name, x, fade_out=.3, max_seconds=16):
    x = x[: int(max_seconds * SR)]
    n = int(SR * fade_out)
    x = norm(x - np.mean(x))
    x[:int(SR * .004)] *= np.linspace(0, 1, int(SR * .004))
    x[-n:] *= np.linspace(1, 0, n)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"{name}.wav  {len(x) / SR:.1f} s")


def main(hits, creature, ghost, ambient):
    hits, creature = Path(hits), Path(creature)
    hit = lambda group, i: trim(load(hits / "Sound" / "Pitches" / group / f"{group} {i}.wav"))
    cs = lambda name, speed=1.0: trim(load(creature / f"{name}.ogg", speed))
    bass, deep, mid = hit("Bassy", 5), hit("Very Bassy", 3), hit("Mid", 6)

    write("scream_2", reverb(mix((cs("scream_01"), 0, 1.0), (bass, 0, .55), (cs("scream_01", .85), .05, .5)), 1.8, .4), 1.2)
    write("scream_3", reverb(mix((cs("scream_02"), 0, 1.0), (mid, 0, .5), (cs("scream_02", .8), .08, .45)), 1.8, .4), 1.2)
    write("scream_4", reverb(mix((cs("scream_01", .6), 0, 1.0), (deep, 0, .7), (cs("scream_02", .75), .12, .6)), 2.2, .45), 1.5)
    write("roar", reverb(mix((cs("monster_04"), 0, 1.0), (cs("roar_02", .8), .1, .8), (deep, 0, .6)), 1.6, .4), 1.0)
    write("growl_2", reverb(mix((cs("monster_07", .8), 0, 1.0), (cs("monster_06", .7), .5, .8), (hit("Very Bassy", 1), 0, .5)), 1.6, .4), 1.0)
    write("hit_bass", drive(norm(bass), 1.4), .6)
    write("breath", reverb(norm(bandpass(load(ghost), 120, 9000)), 1.6, .35), .8)
    write("ambience", norm(load(ambient)), 2.0, 16)


if __name__ == "__main__":
    main(*sys.argv[1:5])

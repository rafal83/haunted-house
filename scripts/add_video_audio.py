"""Give the bundled videos their soundtrack, synchronised with the pictures.

Build machine only: numpy and ffmpeg (a copy ships with the imageio-ffmpeg wheel).
The video stream is copied untouched; the audio is mixed from the sounds already in media/.
Run generate_horror_audio.py, build_cc0_media.py and generate_horror_video.py first.
Also writes apparition_soft.mp4 and surveillance_soft.mp4 (no scream) for the Familiale profile.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave
import numpy as np
from generate_horror_audio import RNG, SR, bandpass, drive

MEDIA = Path(__file__).resolve().parents[1] / "custom_components" / "haunted_house" / "media"


def ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load(name):
    with wave.open(str(MEDIA / f"{name}.wav")) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        rate = w.getframerate()
    if rate != SR:
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / rate)), np.arange(len(x)), x)
    return x


class Track:
    def __init__(self, seconds):
        self.seconds = seconds
        self.x = np.zeros(int(seconds * SR))

    def place(self, sound, at, gain=1.0, fade_in=0.0, fade_out=0.0, length=None):
        sound = np.array(sound[: int(length * SR)] if length else sound, dtype=np.float32)
        if fade_in:
            n = min(len(sound), int(fade_in * SR))
            sound[:n] *= np.linspace(0, 1, n)
        if fade_out:
            n = min(len(sound), int(fade_out * SR))
            sound[-n:] *= np.linspace(1, 0, n)
        start = int(at * SR)
        end = min(len(self.x), start + len(sound))
        if start < end:
            self.x[start:end] += sound[: end - start] * gain
        return self

    def hush(self, start, end, ramp=.15):
        """Cut everything already placed between start and end seconds (a blackout in the picture)."""
        env = np.ones(len(self.x))
        a, b, r = int(start * SR), int(end * SR), int(ramp * SR)
        env[max(0, a - r):a] = np.linspace(1, 0, a - max(0, a - r))
        env[a:b] = 0
        self.x *= env
        return self

    def wav(self, path):
        x = self.x - np.mean(self.x)
        x = np.tanh(x * 1.1)
        x = x / max(1e-9, np.max(np.abs(x))) * .92
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((x * 32767).astype("<i2").tobytes())


def static_noise(seconds, lo=600, hi=9000, level=1.0):
    return bandpass(RNG.uniform(-1, 1, int(seconds * SR)), lo, hi) * level


def hum(seconds, level=.08):
    t = np.arange(int(seconds * SR)) / SR
    return level * (np.sin(2 * np.pi * 50 * t) + .5 * np.sin(2 * np.pi * 100 * t))


def jumpscare(scary=True):
    t = Track(8)
    t.place(load("drone"), 0, .55, fade_in=3, length=8)
    t.place(load("creak"), 1.6, .5)
    t.place(load("footsteps"), 2.2, .5, length=3)
    t.place(load("breath"), 3.2, .35, fade_in=.5)
    t.hush(4.4, 5.15)  # the lights die: dead silence
    t.place(load("hit_bass"), 5.1, .9, length=3)
    t.place(load("scream_2"), 5.15, 1.0)
    t.place(load("growl"), 6.0, .5, fade_out=1.5)
    t.place(static_noise(1.4, level=.4), 6.6, 1.0, fade_out=1.4)
    return t


def surveillance(scary=True):
    t = Track(8)
    t.place(static_noise(8, 2000, 9000, .12), 0, 1.0)
    t.place(hum(8), 0, 1.0)
    t.place(load("breath"), .9, .45 if scary else .35)
    t.place(load("whisper"), 3.0, .4, length=4)
    for k in range(1, 7):  # the picture breaks up every 1.25 s
        t.place(static_noise(.16, level=.8), 1.25 * k, .6)
    if scary:
        t.place(load("hit_bass"), 6.35, .8, length=3)
        t.place(load("scream_3"), 6.4, .9)
    else:
        t.place(load("ambience"), 5.0, .4, fade_in=1, fade_out=1, length=3)
    return t


def static_ghost(scary=True):
    t = Track(7)
    t.place(static_noise(7, 400, 9000, .5), 0, 1.0, fade_out=.5)
    for at, kind in ((2.0, "hit_bass"), (4.1, "hit_bass"), (5.4, "scream_4")):
        t.place(load(kind), at, .9 if kind == "hit_bass" else 1.0, length=2.5 if kind == "hit_bass" else None)
    t.place(load("whisper"), 3.0, .35, length=1.5)
    return t


def apparition(scary=True):
    t = Track(8)
    wind = static_noise(8, 100, 700, 2.5) * (.5 + .5 * np.sin(2 * np.pi * .25 * np.arange(int(8 * SR)) / SR))
    t.place(wind, 0, .45, fade_in=1.5)
    t.place(load("drone"), 0, .3, fade_in=2, length=8)
    t.place(load("whisper"), 1.4, .55)
    t.place(load("breath"), 4.0, .5)
    if scary:
        t.place(load("growl"), 4.8, .55)
        t.place(load("hit_bass"), 6.25, .8, length=3)
        t.place(load("scream"), 6.3, .9)
    else:
        t.place(load("ambience"), 4.5, .45, fade_in=1, length=3.5)
    t.place(np.zeros(1), 0)
    t.x[int(7.4 * SR):] *= np.linspace(1, 0, len(t.x) - int(7.4 * SR))
    return t


def kids():
    t = Track(6)
    for at in (0, 2, 4):
        t.place(load("kids"), at, .9)
    return t


VIDEOS = [("jumpscare", jumpscare, "jumpscare", True), ("surveillance", surveillance, "surveillance", True),
          ("static_ghost", static_ghost, "static_ghost", True), ("apparition", apparition, "apparition", True),
          ("surveillance_soft", surveillance, "surveillance", False), ("apparition_soft", apparition, "apparition", False),
          ("kids", lambda scary=True: kids(), "kids", True)]


def mux(video, audio, out):
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-i", str(audio),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-ac", "1",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="haunted_audio_") as tmp:
        # Take the picture from each original once, so re-running never stacks soundtracks.
        sources = {}
        for name in {v[2] for v in VIDEOS}:
            sources[name] = Path(tmp) / f"{name}_video.mp4"
            shutil.copy(MEDIA / f"{name}.mp4", sources[name])
        for name, build, source, scary in VIDEOS:
            wav = Path(tmp) / f"{name}.wav"
            build(scary).wav(wav)
            mux(sources[source], wav, MEDIA / f"{name}.mp4")
            print(f"{name}.mp4  {(MEDIA / f'{name}.mp4').stat().st_size // 1024} KB")

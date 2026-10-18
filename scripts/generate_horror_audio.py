"""Synthesise the dark, original sound effects shipped with the integration.

Requires numpy on the build machine only. Everything is procedural (no recordings, no
speech): scream, growl, creak, thunder, footsteps, knocks, whispers, laugh and drone.
"""
from pathlib import Path
import wave
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "haunted_house" / "media"
SR = 32000
RNG = np.random.default_rng(1313)


def t_axis(seconds):
    return np.arange(int(SR * seconds)) / SR


def noise(seconds):
    return RNG.uniform(-1, 1, int(SR * seconds))


def bandpass(x, lo, hi, slope=300.0):
    """FFT band-pass with a soft skirt, so there is no ringing."""
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = np.clip(1 - np.maximum(lo - f, 0) / slope, 0, 1) * np.clip(1 - np.maximum(f - hi, 0) / slope, 0, 1)
    return np.fft.irfft(spectrum * gain, len(x))


def reverb(x, seconds=1.4, wet=.45):
    n = int(SR * seconds)
    impulse = RNG.uniform(-1, 1, n) * np.exp(-np.linspace(0, 7, n))
    impulse = bandpass(impulse, 80, 5000)
    size = len(x) + n
    wet_signal = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(impulse, size), size)
    wet_signal /= max(1e-9, np.max(np.abs(wet_signal)))
    dry = np.pad(x, (0, n))
    return dry * (1 - wet) + wet_signal * np.max(np.abs(x)) * wet * 1.6


def drive(x, amount):
    return np.tanh(x * amount) / np.tanh(amount)


def fit(x, seconds):
    n = int(SR * seconds)
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def fade(x, attack=.01, release=.15):
    a, r = int(SR * attack), int(SR * release)
    env = np.ones(len(x))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    return x * env


def harmonic(freq, count=24, tilt=1.0):
    """Band-limited sawtooth-like voice with a per-sample frequency curve."""
    phase = 2 * np.pi * np.cumsum(freq) / SR
    out = np.zeros(len(freq))
    for k in range(1, count + 1):
        out += np.sin(k * phase) / k ** tilt * (k * freq < SR / 2)
    return out


def smooth_noise(seconds, rate):
    """Slowly wandering random curve in [-1, 1]."""
    points = RNG.uniform(-1, 1, int(seconds * rate) + 2)
    return np.interp(t_axis(seconds), np.arange(len(points)) / rate, points)


def scream():
    s = 3.4
    t = t_axis(s)
    glide = 520 + 900 * np.sin(np.clip(t / 1.1, 0, 1) * np.pi / 2) - 250 * np.clip((t - 1.8) / 1.5, 0, 1)
    glide *= 1 + .035 * np.sin(2 * np.pi * 6.2 * t) + .02 * smooth_noise(s, 18)
    voice = harmonic(glide, 28, .8) + .7 * harmonic(glide * 1.5 * (1 + .03 * smooth_noise(s, 9)), 18, 1.0)
    voice += .6 * harmonic(glide * .5, 20, .7)
    formants = bandpass(voice, 700, 1200) * 1.2 + bandpass(voice, 2300, 3300) * 1.4 + bandpass(voice, 4200, 6000) * .6
    rasp = bandpass(noise(s), 1500, 7000) * (.5 + .5 * np.sin(2 * np.pi * 70 * t)) * .7
    env = np.minimum(1, t / .05) * np.exp(-np.clip(t - 2.2, 0, None) * 1.8)
    env *= .8 + .2 * np.sin(2 * np.pi * 9 * t)
    return reverb(drive((formants + rasp) * env, 5), 1.8, .35)


def growl():
    s = 3.6
    t = t_axis(s)
    freq = 62 + 14 * smooth_noise(s, 6) + 25 * np.exp(-t)
    body = harmonic(freq, 40, .6) * (.6 + .4 * np.sign(np.sin(2 * np.pi * 27 * t + 2 * smooth_noise(s, 5))))
    breath = bandpass(noise(s), 180, 900) * (.5 + .5 * np.sin(2 * np.pi * 11 * t))
    env = np.sin(np.pi * np.clip(t / s, 0, 1)) ** .6
    return reverb(drive((body + breath * .9) * env, 6), 1.2, .3)


def creak():
    s = 3.2
    t = t_axis(s)
    slip = (smooth_noise(s, 14) + 1) / 2
    freq = 140 + 420 * slip + 160 * np.sin(2 * np.pi * .7 * t)
    pulses = (np.sin(2 * np.pi * np.cumsum(25 + 90 * slip) / SR) > .3).astype(float)
    wood = harmonic(freq, 30, .5) * (.4 + .6 * pulses)
    wood = bandpass(wood, 260, 3200) + .3 * bandpass(noise(s), 800, 2600) * pulses
    env = np.sin(np.pi * np.clip(t / s, 0, 1)) ** .8
    return reverb(drive(wood * env, 3.5), 1.6, .35)


def thunder():
    s = 7.0
    t = t_axis(s)
    crack = bandpass(noise(.35), 600, 9000) * np.exp(-np.linspace(0, 9, int(SR * .35)))
    rumble = bandpass(noise(s), 18, 130, 40) * (.55 + .45 * np.sin(2 * np.pi * (2.4 + .6 * smooth_noise(s, 3)) * t))
    swell = (1 - np.exp(-t / .5)) * np.exp(-t / 2.4)
    rolling = bandpass(noise(s), 90, 380) * np.exp(-t / 1.4) * .5
    x = rumble * swell * 3.5 + rolling * (1 + np.sin(2 * np.pi * 5 * t))
    x[: len(crack)] += crack * 1.8
    return reverb(drive(x, 2.2), 2.4, .4)


def thud(freq=58, length=.55):
    n = int(SR * length)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (freq + 40 * np.exp(-t * 28)) * t) * np.exp(-t * 9)
    knock = bandpass(RNG.uniform(-1, 1, n), 120, 900) * np.exp(-t * 26) * .8
    return body * 1.2 + knock


def place(buffer, sound, at, gain=1.0):
    start = int(at * SR)
    end = min(len(buffer), start + len(sound))
    buffer[start:end] += sound[: end - start] * gain


def footsteps():
    s = 5.4
    out = np.zeros(int(SR * s))
    at = .25
    for i in range(5):
        place(out, thud(52 + RNG.uniform(-6, 8), .6), at, 1 - .08 * i * (i > 2))
        place(out, bandpass(RNG.uniform(-1, 1, int(SR * .25)), 700, 2600) * np.exp(-np.linspace(0, 8, int(SR * .25))) * .25, at + .03)
        at += RNG.uniform(.85, 1.15)
    return reverb(drive(out, 1.8), 1.8, .4)


def knock():
    s = 4.2
    out = np.zeros(int(SR * s))
    for at in (.2, .75, 1.3, 2.35, 2.62, 2.9, 3.15):
        sound = thud(95 + RNG.uniform(-8, 8), .38) + .5 * bandpass(RNG.uniform(-1, 1, int(SR * .38)), 350, 1800) * np.exp(-np.linspace(0, 16, int(SR * .38)))
        place(out, sound, at, 1.0)
    return reverb(drive(out, 2.2), 1.5, .38)


def whisper():
    s = 5.0
    t = t_axis(s)
    out = np.zeros(len(t))
    for layer in range(2):
        at = .2 + layer * .35
        while at < s - .5:
            length = RNG.uniform(.09, .26)
            n = int(SR * length)
            burst = RNG.uniform(-1, 1, n)
            if RNG.random() < .55:
                burst = bandpass(burst, 3200, 7500, 600) * 1.2
            else:
                burst = bandpass(burst, 350, 1700, 250)
            burst *= np.hanning(n)
            place(out, burst, at, RNG.uniform(.4, 1.0))
            at += length + RNG.uniform(.03, .2) + (.35 if RNG.random() < .2 else 0)
    out = bandpass(out, 220, 8000) * (.7 + .3 * np.sin(2 * np.pi * .4 * t))
    return reverb(out, 2.0, .5)


def laugh():
    s = 4.2
    t = t_axis(s)
    out = np.zeros(len(t))
    base = 150
    at, k = .25, 0
    while at < s - .6 and k < 7:
        length = RNG.uniform(.16, .26)
        n = int(SR * length)
        tt = np.arange(n) / SR
        pitch = (base - 12 * k) * (1.25 - .45 * tt / length) * (1 + .05 * np.sin(2 * np.pi * 28 * tt))
        voice = harmonic(pitch, 26, .9)
        voice = bandpass(voice, 650, 950) * 1.3 + bandpass(voice, 1100, 1500) * .9 + bandpass(voice, 2400, 3400) * .5
        voice *= np.sin(np.pi * np.arange(n) / n) ** .7
        place(out, voice, at, 1.0 - .06 * k)
        at += length + RNG.uniform(.11, .2)
        k += 1
    out *= 1 + .35 * np.sin(2 * np.pi * 7.5 * t)
    return reverb(drive(out, 3.2), 1.7, .42)


def drone():
    s = 8.0
    t = t_axis(s)
    low = np.sin(2 * np.pi * 41 * t) + .8 * np.sin(2 * np.pi * 43.6 * t) + .5 * np.sin(2 * np.pi * 27.5 * t)
    tritone = .55 * harmonic(np.full(len(t), 58.0) * (1 + .004 * smooth_noise(s, 3)), 14, 1.1)
    tritone += .45 * harmonic(np.full(len(t), 82.4) * (1 + .006 * smooth_noise(s, 4)), 12, 1.2)
    shimmer = bandpass(noise(s), 1800, 2400) * .06 * (.5 + .5 * np.sin(2 * np.pi * .3 * t))
    wind = bandpass(noise(s), 100, 520) * (.4 + .4 * smooth_noise(s, 1.5)) * .5
    x = (low + tritone) * (.6 + .4 * np.sin(2 * np.pi * .25 * t)) + wind + shimmer
    return drive(x, 1.6) * np.minimum(1, np.minimum(t / 1.5, (s - t) / 1.5))


SOUNDS = {"scream": scream, "growl": growl, "creak": creak, "thunder": thunder, "footsteps": footsteps,
          "knock": knock, "whisper": whisper, "laugh": laugh, "drone": drone}


def write(name, x):
    x = np.nan_to_num(x)
    x -= np.mean(x)
    x = fade(x, .01, .25)
    x = x / max(1e-9, np.max(np.abs(x))) * .93
    data = (x * 32767).astype("<i2")
    with wave.open(str(OUT / f"{name}.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(data.tobytes())
    return len(x) / SR


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        print(f"{name}.wav  {write(name, make()):.1f} s")

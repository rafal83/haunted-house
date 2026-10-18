"""Render the scary, original videos shipped with the integration.

Build machine only: numpy, Pillow and ffmpeg (a copy ships with the imageio-ffmpeg wheel).
All imagery is procedural. Faces are drawn shapes, not photographs of anyone.
Usage: python generate_horror_video.py [name ...]   (default: all)
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "haunted_house" / "media"
W, H, FPS = 854, 480, 24
RNG = np.random.default_rng(666)
YY, XX = np.mgrid[0:H, 0:W]
VIGNETTE = np.clip(1.25 - 1.55 * (((XX - W / 2) / (W / 2)) ** 2 + ((YY - H / 2) / (H / 2)) ** 2) ** .5 * .75, .05, 1)[..., None]


def font(size):
    for name in ("arialbd.ttf", "DejaVuSansMono-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def to_array(img):
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def finish(frame, grain=16, vignette=True, scan=True):
    if vignette:
        frame = frame * VIGNETTE
    if scan:
        frame[::2] *= .86
    frame += RNG.normal(0, grain, (H, W, 1))
    return np.clip(frame, 0, 255)


def glitch(frame, amount):
    """Horizontal tearing plus red/blue channel offset."""
    out = frame.copy()
    for _ in range(int(min(amount, 1.5) * 9)):
        y = int(RNG.integers(0, H - 8))
        h = int(RNG.integers(2, 18))
        out[y:y + h] = np.roll(out[y:y + h], int(RNG.integers(-60, 60) * min(amount, 1.2)), axis=1)
    shift = min(7, int(6 * amount))
    if shift:
        out[..., 0] = np.roll(out[..., 0], shift, axis=1)
        out[..., 2] = np.roll(out[..., 2], -shift, axis=1)
    return out


def static(level=1.0, tint=(1, 1, 1)):
    base = RNG.uniform(0, 255, (H, W, 1)) * level
    bands = np.repeat(RNG.uniform(.6, 1.2, (H, 1, 1)), W, axis=1)
    return np.clip(base * bands, 0, 255) * np.array(tint, dtype=np.float32)


def face(height, glow=(255, 40, 30), mouth=1.0, skin=(205, 208, 200)):
    """A pale, hollow-eyed, gaping face on a transparent canvas."""
    w, h = int(height * .62), height
    big = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    W2, H2 = w * 2, h * 2
    for _ in range(90):  # long dark hair, drawn first so the face sits in front of it
        x0 = RNG.uniform(.05, .95) * W2
        d.line([(x0, H2 * .02), (x0 + RNG.uniform(-.2, .2) * W2, H2 * RNG.uniform(.55, 1.0))],
               fill=(8, 8, 10, 255), width=int(RNG.integers(3, 11)))
    d.ellipse((W2 * .12, H2 * .05, W2 * .88, H2 * .93), fill=skin + (255,))
    shade = Image.new("L", (W2, H2), 0)
    ImageDraw.Draw(shade).ellipse((W2 * .2, H2 * .1, W2 * .8, H2 * .88), fill=255)
    shade = shade.filter(ImageFilter.GaussianBlur(H2 * .09))
    mask = np.asarray(shade, dtype=np.float32)[..., None] / 255
    arr = np.asarray(big, dtype=np.float32)
    arr[..., :3] *= (.35 + .65 * mask)
    big = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(big)
    for cx in (.34, .66):  # sunken sockets with a tiny glowing point
        d.ellipse((W2 * (cx - .15), H2 * .26, W2 * (cx + .15), H2 * .46), fill=(4, 2, 3, 255))
        d.ellipse((W2 * (cx - .018), H2 * .355, W2 * (cx + .018), H2 * .385), fill=glow + (255,))
    d.polygon([(W2 * .5, H2 * .42), (W2 * .46, H2 * .6), (W2 * .54, H2 * .6)], fill=(60, 55, 55, 255))
    my0, my1 = H2 * .62, H2 * (.62 + .27 * mouth)
    d.ellipse((W2 * .3, my0, W2 * .7, my1), fill=(2, 0, 0, 255))
    for i in range(9):  # uneven teeth
        x = W2 * (.34 + .32 * i / 8)
        d.polygon([(x - 5, my0 + 6), (x + 5, my0 + 6), (x, my0 + 6 + RNG.uniform(14, 34) * mouth)], fill=(170, 165, 140, 255))
    for cx in (.34, .66):  # cracks running down from the eyes and mouth
        for _ in range(3):
            x, y = W2 * cx, H2 * .45
            pts = [(x, y)]
            for _ in range(6):
                x += RNG.uniform(-14, 14)
                y += RNG.uniform(20, 55)
                pts.append((x, y))
            d.line(pts, fill=(15, 8, 8, 255), width=3)
    return big.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.8))


def paste_center(frame, sprite, cx, cy, tint=None, alpha=1.0):
    img = Image.fromarray(frame.astype(np.uint8), "RGB").convert("RGBA")
    img.alpha_composite(sprite, (int(cx - sprite.width / 2), int(cy - sprite.height / 2)))
    out = np.asarray(img.convert("RGB"), dtype=np.float32)
    if tint is not None:
        out = out * np.array(tint, dtype=np.float32)
    return frame * (1 - alpha) + out * alpha


FACE_CACHE = {}


def cached_face(height, **kw):
    key = (height // 12, tuple(sorted(kw.items())))
    if key not in FACE_CACHE:
        FACE_CACHE[key] = face(max(40, key[0] * 12), **kw)
    return FACE_CACHE[key]


def corridor(t, flicker, zoom):
    img = Image.new("RGB", (W, H), (6, 6, 8))
    d = ImageDraw.Draw(img)
    vx, vy = W / 2 + 6 * np.sin(t * 1.3), H * .47
    lit = int(110 + 140 * flicker)
    d.polygon([(0, 0), (W, 0), (vx + 40, vy - 30), (vx - 40, vy - 30)], fill=(int(lit * .12),) * 3)  # ceiling
    d.polygon([(0, H), (W, H), (vx + 40, vy + 30), (vx - 40, vy + 30)], fill=(int(lit * .2), int(lit * .2), int(lit * .18)))  # floor
    d.polygon([(0, 0), (vx - 40, vy - 30), (vx - 40, vy + 30), (0, H)], fill=(int(lit * .16), int(lit * .16), int(lit * .18)))
    d.polygon([(W, 0), (vx + 40, vy - 30), (vx + 40, vy + 30), (W, H)], fill=(int(lit * .13), int(lit * .13), int(lit * .15)))
    for k in range(14):  # door frames rushing past: perspective rectangles
        s = (k + (t * .55 * zoom) % 1) ** 1.9 / 13 ** 1.9
        s = max(s, .02)
        half_w, half_h = W * (.03 + 1.4 * s) / 2, H * (.05 + 1.5 * s) / 2
        c = int(min(255, lit * (.5 + .9 * s)))
        d.rectangle((vx - half_w, vy - half_h, vx + half_w, vy + half_h), outline=(c, c, c + 6), width=max(1, int(1 + 3 * s)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            d.line((vx, vy, vx + sx * W, vy + sy * H), fill=(int(lit * .3),) * 3, width=1)
    d.rectangle((vx - 14, vy - 22, vx + 14, vy + 22), fill=(int(lit * 1.6),) * 3)  # far doorway
    return to_array(img)


def jumpscare():
    frames, total = [], 8 * FPS
    for i in range(total):
        t = i / FPS
        flick = float(np.clip(.5 + .5 * np.sin(t * 9) * np.sin(t * 3.7) + RNG.normal(0, .25), 0, 1))
        if t < 4.4:
            f = corridor(t, flick, 1 + t * .25)
            sprite = cached_face(int(50 + 150 * (t / 4.4) ** 2.2), mouth=.3)  # a figure creeping down the hall
            f = paste_center(f, sprite, W / 2 + 4 * np.sin(t * 7), H * .5 + 6, alpha=.55 + .35 * flick)
            f = finish(f, 18)
            if RNG.random() < .06 * t:
                f = glitch(f, .4)
        elif t < 5.15:  # everything dies
            f = finish(np.zeros((H, W, 3), np.float32) + 3, 12) * (1 if RNG.random() < .12 else .25)
        elif t < 5.9:  # the face slams into the lens
            k = (t - 5.15) / .75
            big = cached_face(int(H * (.55 + .65 * k ** .5)), mouth=1.0)
            f = np.full((H, W, 3), 6, np.float32)
            f = paste_center(f, big, W / 2 + RNG.normal(0, 8), H * .5 + RNG.normal(0, 8), tint=(1.15, .72, .7))
            f = glitch(finish(f, 22, scan=False), .25 + .3 * k)
        elif t < 6.6:  # lingering, shaking
            big = cached_face(int(H * 1.2), mouth=1.0)
            f = np.full((H, W, 3), 4, np.float32)
            f = paste_center(f, big, W / 2 + RNG.normal(0, 10), H * .5 + RNG.normal(0, 10), tint=(1.35, .55, .5))
            f = glitch(finish(f, 30, scan=False), .35 + .5 * RNG.random())
        else:
            f = finish(static(.9, (1, .85, .85)) * np.clip(1 - (t - 6.6) / 1.4, 0, 1), 6, scan=False)
        frames.append(f)
    return frames


def surveillance():
    frames, total = [], 8 * FPS
    stamp, small = font(22), font(18)
    for i in range(total):
        t = i / FPS
        img = Image.new("RGB", (W, H), (18, 40, 24))
        d = ImageDraw.Draw(img)
        d.polygon([(0, H * .62), (W, H * .62), (W, H), (0, H)], fill=(26, 56, 34))  # floor
        d.rectangle((W * .38, H * .1, W * .62, H * .64), fill=(8, 18, 10))  # doorway
        d.rectangle((W * .38, H * .1, W * .62, H * .64), outline=(60, 120, 70), width=4)
        d.rectangle((W * .06, H * .3, W * .24, H * .62), fill=(22, 48, 28), outline=(50, 100, 60), width=3)  # shelf
        d.line((0, H * .62, W * .38, H * .64), fill=(44, 90, 52), width=3)
        d.line((W, H * .62, W * .62, H * .64), fill=(44, 90, 52), width=3)
        f = to_array(img)
        step = min(5, int(t / 1.25))  # the figure is closer every time the picture breaks up
        height = int(110 + step * 62 + 40 * max(0, t - 6.4) ** 1.5)
        if t > .8:
            sprite = cached_face(height, glow=(220, 255, 220), mouth=.15 + .12 * step, skin=(150, 175, 150))
            f = paste_center(f, sprite, W / 2 + (0 if step < 5 else RNG.normal(0, 10)), H * .64 - height * .25, alpha=1.0)
        f = f * np.array([.55, 1.0, .6], dtype=np.float32) * (1 + .15 * np.sin(t * 40) * (RNG.random() < .2))
        if (i % int(FPS * 1.25)) < 3 and t > .8:
            f = glitch(f, .9)
            f = f * .6 + static(.5, (.4, 1, .5)) * .4
        f = finish(f, 22)
        img2 = Image.fromarray(f.astype(np.uint8), "RGB")
        dd = ImageDraw.Draw(img2)
        sec = 3 * 60 + 12 + int(t)
        dd.text((22, 18), f"CAM 02   2026-10-18  03:{sec // 60:02d}:{sec % 60:02d}", font=stamp, fill=(150, 255, 160))
        if int(t * 2) % 2 == 0:
            dd.ellipse((W - 78, 22, W - 62, 38), fill=(235, 40, 40))
        dd.text((W - 54, 18), "REC", font=small, fill=(235, 90, 90))
        dd.text((22, H - 36), "NO SIGNAL FROM CAM 03", font=small, fill=(120, 200, 130))
        frames.append(np.asarray(img2, dtype=np.float32))
    return frames


def static_ghost():
    frames, total = [], 7 * FPS
    blips = {int(2.0 * FPS): 3, int(4.1 * FPS): 4, int(5.4 * FPS): 12}
    live = {}
    for i in range(total):
        f = static(1.0)
        for start, length in blips.items():
            if start <= i < start + length:
                big = cached_face(int(H * (.8 if length < 6 else 1.35)), mouth=1.0)
                inv = length < 6
                layer = paste_center(np.full((H, W, 3), 12, np.float32), big, W / 2, H * .5,
                                     tint=(1, 1, 1) if inv else (1.4, .5, .45))
                f = 255 - layer if inv else layer * .85 + f * .25
        if RNG.random() < .1:
            f = glitch(f, .6)
        f = finish(f * (1 if i < total - 12 else max(0, (total - i) / 12)), 6, scan=True)
        frames.append(f)
    return frames


def apparition():
    frames, total = [], 8 * FPS
    for i in range(total):
        t = i / FPS
        img = Image.new("RGB", (W, H), (5, 7, 12))
        d = ImageDraw.Draw(img)
        d.polygon([(W * .62, H * .12), (W * .86, H * .12), (W * .9, H * .6), (W * .58, H * .6)], fill=(26, 34, 56))  # moonlit window
        d.line((W * .74, H * .12, W * .74, H * .6), fill=(5, 7, 12), width=5)
        d.line((W * .58, H * .36, W * .9, H * .36), fill=(5, 7, 12), width=5)
        f = to_array(img)
        approach = np.clip((t - 1.2) / 5.5, 0, 1)
        height = int(120 + 330 * approach ** 1.6)
        vis = np.clip(np.sin(t * 2.1) * .5 + .6, 0, 1) * np.clip(t / 1.5, 0, 1) * (RNG.random() > .08)
        sprite = cached_face(height, glow=(255, 30, 20), mouth=.4 + .6 * approach, skin=(185, 195, 215))
        f = paste_center(f, sprite, W * .3 + 120 * (1 - approach) + 4 * np.sin(t * 5), H * .55, alpha=.55 * vis + .1)
        f = finish(f * (.85 + .15 * np.sin(t * 11) * RNG.random()), 18)
        if t > 6.3:
            f = glitch(f, min(1.2, (t - 6.3) * .9))
        if t > 7.4:
            f = f * np.clip(1 - (t - 7.4) / .6, 0, 1)
        frames.append(f)
    return frames


VIDEOS = {"jumpscare": jumpscare, "surveillance": surveillance, "static_ghost": static_ghost, "apparition": apparition}


def encode(name, frames):
    with tempfile.TemporaryDirectory(prefix="haunted_video_") as tmp:
        for i, frame in enumerate(frames):
            Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8), "RGB").save(Path(tmp) / f"{i:05}.png")
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
                        "-i", str(Path(tmp) / "%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "slow",
                        "-crf", "29", "-movflags", "+faststart", str(OUT / f"{name}.mp4")], check=True)
        if "--stills" in sys.argv:
            for second in (1, 3, 5.4, 5.8, 6.2):
                idx = min(len(frames) - 1, int(second * FPS))
                shutil.copy(Path(tmp) / f"{idx:05}.png", OUT.parents[2] / "scripts" / f"_still_{name}_{second}.png")
    print(f"{name}.mp4  {len(frames) / FPS:.1f} s  {(OUT / f'{name}.mp4').stat().st_size // 1024} KB")


if __name__ == "__main__":
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(VIDEOS)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        encode(name, VIDEOS[name]())

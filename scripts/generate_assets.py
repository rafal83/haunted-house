"""Rebuild original, procedural demo media. Requires Pillow and ffmpeg on the build machine only."""
import math
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import wave
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'www' / 'haunted_house'
OUT.mkdir(parents=True, exist_ok=True)
SR = 22050


def audio(kind, t, rng):
    noise = rng.uniform(-1, 1)
    if kind == 'thunder':
        return .18 * math.exp(-t * 1.7) * (noise * .5 + math.sin(t * 2 * math.pi * 48))
    if kind in ('footsteps', 'knock'):
        hit = t % (.65 if kind == 'footsteps' else .4)
        return .25 * math.exp(-hit * 32) * (math.sin(t * 2 * math.pi * 110) + .25 * noise)
    if kind == 'whisper':
        return .08 * noise * (math.sin(t * 4) ** 2) * math.sin(t * 2 * math.pi * 500)
    if kind == 'laugh':
        return .12 * math.sin(t * 2 * math.pi * (170 + 30 * math.sin(t * 6))) * max(0, math.sin(t * 16))
    if kind == 'kids':
        note = [523.25, 659.25, 783.99, 1046.5][min(3, int(t * 2))]
        return .12 * math.sin(t * 2 * math.pi * note) * math.exp(-(t % .5) * 7)
    return .1 * math.sin(t * 2 * math.pi * (95 + 15 * math.sin(t * 2))) * math.sin(math.pi * min(1, t / 2))


for name in ['thunder', 'footsteps', 'knock', 'whisper', 'laugh', 'kids', 'drone']:
    rng = random.Random(name)
    samples = []
    for i in range(SR * 2):
        t = i / SR
        fade = min(1, t * 20, (2 - t) * 20)
        samples.append(struct.pack('<h', int(max(-1, min(1, audio(name, t, rng) * fade)) * 32767)))
    with wave.open(str(OUT / f'{name}.wav'), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(b''.join(samples))


def frame(kind, t):
    im = Image.new('RGB', (640, 360), '#040509')
    d = ImageDraw.Draw(im)
    if kind == 'surveillance':
        for x, y in [(20, 25), (330, 25), (20, 190), (330, 190)]:
            d.rectangle((x, y, x + 285, y + 145), fill='#101a18', outline='#284c40', width=2)
            d.line((x + 40, y + 135, x + 115, y + 20, x + 200, y + 135), fill='#243c33', width=2)
            d.text((x + 8, y + 8), 'CAM 0' + str(1 + (x > 20) + 2 * (y > 25)), fill='#8eaf9c')
        d.text((22, 5), 'SIMULATION - SIGNAL INSTABLE', fill='#8eaf9c')
        if t > 2:
            x = 470 + int(15 * math.sin(t))
            d.ellipse((x - 18, 225, x + 18, 265), fill='#697d72')
            d.polygon([(x - 18, 250), (x + 18, 250), (x + 30, 320), (x - 30, 320)], fill='#5c6c63')
    elif kind == 'kids':
        x, y = 320 + int(20 * math.sin(t * 2)), 175 + int(8 * math.sin(t * 3))
        d.rounded_rectangle((x - 8, y - 110, x + 7, y - 70), radius=4, fill='#3e914c')
        d.ellipse((x - 95, y - 80, x + 95, y + 90), fill='#dc7013')
        d.ellipse((x - 60, y - 80, x + 60, y + 90), outline='#f5a322', width=3)
        d.polygon([(x - 60, y - 5), (x - 35, y - 35), (x - 15, y - 5)], fill='#ffdf72')
        d.polygon([(x + 15, y - 5), (x + 35, y - 35), (x + 60, y - 5)], fill='#ffdf72')
        d.arc((x - 55, y, x + 55, y + 55), 0, 180, fill='#ffdf72', width=9)
        d.text((240, 315), 'LA CITROUILLE MAGIQUE', fill='#e3a351')
    else:
        # A simple spectral silhouette fading into a dark frame, not a real person.
        x = 320 + int(60 * math.sin(t))
        y = 180 + int(10 * math.sin(t * 3))
        brightness = int(150 * math.sin(math.pi * t / 6) ** 2)
        color = (int(brightness * .65), brightness, int(brightness * .85))
        d.ellipse((x - 43, y - 95, x + 43, y - 10), fill=color)
        d.polygon([(x - 40, y - 60), (x + 40, y - 60), (x + 90, y + 100),
                   (x + 45, y + 80), (x + 15, y + 110), (x - 20, y + 85), (x - 85, y + 110)], fill=color)
        d.ellipse((x - 23, y - 68, x - 12, y - 48), fill='#050909')
        d.ellipse((x + 12, y - 68, x + 23, y - 48), fill='#050909')
    return im


for kind in ['apparition', 'surveillance', 'kids']:
    with tempfile.TemporaryDirectory(prefix='haunted_frames_') as tmp:
        for i in range(72):
            frame(kind, i / 12).save(Path(tmp) / f'{i:04}.png')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '12',
                        '-i', str(Path(tmp) / '%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-crf', '25', '-movflags', '+faststart', str(OUT / f'{kind}.mp4')], check=True)
print('Generated seven 2-second WAV files and three 6-second MP4 videos:', OUT)

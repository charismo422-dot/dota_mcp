"""Generate the stage 10 cutscene assets of mcp_lab: three 1920x1080 slides, a 40 s theme and an .mp3 sting.

Usage: python make_lab_cutscene.py <content/dota_addons/mcp_lab>
Writes:
  panorama/images/custom_game/cutscene/{rift,mage,hunters}.png  (procedural art, no text: subtitles are localized)
  sounds/mcp_lab/cutscene_theme.wav                              (40 s drone + bell hits on the shot changes)
  sounds/mcp_lab/cutscene_boom.mp3                               (impact for the hunters slide; needs ffmpeg in PATH)
Needs Pillow (images) and ffmpeg (mp3). Deterministic output (fixed random seed).
"""

import array
import math
import random
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1920, 1080
RATE = 44100
THEME_SECONDS = 40.0
SHOT_TIMES = (0.0, 7.0, 16.0, 24.0, 33.0)  # must match CUTSCENE_SHOTS in mcp_lab_cutscene.lua


# ---------- images ----------

def gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def _add(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.add(a, b)


def stars(img: Image.Image, rng: random.Random, count: int, max_y: int) -> None:
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x, y = rng.randrange(W), rng.randrange(max_y)
        v = rng.randrange(120, 255)
        r = rng.choice((0, 0, 0, 1, 1, 2))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, min(255, v + 30)))


def ridge(rng: random.Random, base: int, amp: int, step: int) -> list:
    pts, y = [(0, H)], base
    for x in range(0, W + step, step):
        y = max(base - amp, min(base + amp, y + rng.randint(-amp // 3, amp // 3)))
        pts.append((x, y))
    pts.append((W, H))
    return pts


def slide_rift(rng: random.Random) -> Image.Image:
    img = gradient((8, 4, 24), (34, 10, 52))
    stars(img, rng, 900, H)
    cx, cy = W // 2, 470
    img = _add(img, _blurred([cx - 520, cy - 420, cx + 520, cy + 420], (70, 10, 110), 120))
    img = _add(img, _blurred([cx - 140, cy - 380, cx + 140, cy + 380], (150, 40, 220), 60))
    img = _add(img, _blurred([cx - 40, cy - 330, cx + 40, cy + 330], (230, 170, 255), 18))
    d = ImageDraw.Draw(img)
    for i in range(70):  # debris spiralling into the rift
        a = i * 0.55
        r = 90 + i * 7
        x, y = cx + math.cos(a) * r * 1.4, cy + math.sin(a) * r * 0.6
        s = rng.randint(3, 9)
        d.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s * 0.7, y)], fill=(120 + i, 80, 200))
    d.polygon(ridge(rng, 860, 60, 40), fill=(10, 6, 18))
    d.polygon(ridge(rng, 960, 30, 25), fill=(4, 2, 8))
    return img


def slide_mage(rng: random.Random) -> Image.Image:
    img = gradient((10, 30, 60), (150, 200, 235))
    img = _add(img, _blurred([1250, 120, 1750, 620], (90, 120, 140), 140))
    d = ImageDraw.Draw(img)
    for _ in range(26):  # crystal shards
        x = rng.randrange(-100, W + 100)
        h = rng.randint(220, 620)
        w = rng.randint(50, 130)
        lean = rng.randint(-120, 120)
        c = rng.randint(140, 220)
        d.polygon([(x - w, H), (x + lean, H - h), (x + w, H)], fill=(c - 60, c, 255))
        d.line([(x + lean, H - h), (x, H)], fill=(230, 250, 255), width=3)
    img = img.filter(ImageFilter.GaussianBlur(1))
    d = ImageDraw.Draw(img)
    mx, my = 760, 980  # mage silhouette on a crystal ledge, staff raised
    d.polygon([(mx - 90, my), (mx - 30, my - 300), (mx + 30, my - 300), (mx + 90, my)], fill=(12, 20, 40))
    d.ellipse([mx - 38, my - 380, mx + 38, my - 300], fill=(12, 20, 40))
    d.line([(mx + 40, my - 260), (mx + 170, my - 560)], fill=(12, 20, 40), width=14)
    img = _add(img, _blurred([mx + 120, my - 620, mx + 220, my - 520], (160, 230, 255), 25))
    d = ImageDraw.Draw(img)
    for _ in range(700):  # snow
        x, y, r = rng.randrange(W), rng.randrange(H), rng.choice((1, 2, 2, 3))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(235, 245, 255))
    return img


def slide_hunters(rng: random.Random) -> Image.Image:
    img = gradient((40, 0, 0), (140, 30, 10))
    img = _add(img, _blurred([760, 60, 1160, 460], (200, 120, 60), 50))
    d = ImageDraw.Draw(img)
    d.ellipse([820, 120, 1100, 400], fill=(250, 210, 150))
    d.polygon(ridge(rng, 900, 40, 30), fill=(20, 4, 4))
    figures = ((560, 1.0, "sword"), (960, 1.25, "axe"), (1360, 1.0, "fire"))
    for fx, s, weapon in figures:
        base = 1000
        body = [(fx - 110 * s, base), (fx - 60 * s, base - 330 * s), (fx + 60 * s, base - 330 * s), (fx + 110 * s, base)]
        d.polygon(body, fill=(8, 0, 0))
        d.ellipse([fx - 50 * s, base - 430 * s, fx + 50 * s, base - 320 * s], fill=(8, 0, 0))
        if weapon == "sword":
            d.polygon([(fx + 70, base - 200), (fx + 95, base - 210), (fx + 40, base - 620), (fx + 25, base - 610)], fill=(8, 0, 0))
        elif weapon == "axe":
            d.line([(fx - 90 * s, base - 120 * s), (fx - 150 * s, base - 520 * s)], fill=(8, 0, 0), width=16)
            d.pieslice([fx - 260 * s, base - 600 * s, fx - 60 * s, base - 420 * s], 120, 300, fill=(8, 0, 0))
    img = _add(img, _blurred([1360 + 60, 1000 - 360, 1360 + 200, 1000 - 220], (255, 120, 20), 30))  # fire in the hand
    for fx, s, _ in figures:  # glowing eyes
        ey = 1000 - 385 * s
        for ex in (fx - 18 * s, fx + 18 * s):
            img = _add(img, _blurred([ex - 9, ey - 5, ex + 9, ey + 5], (255, 40, 20), 4))
    d = ImageDraw.Draw(img)
    for _ in range(300):  # embers
        x, y, r = rng.randrange(W), rng.randrange(H), rng.choice((1, 1, 2))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, rng.randint(80, 180), 20))
    return img


def _blurred(box, color, radius) -> Image.Image:
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=color)
    return layer.filter(ImageFilter.GaussianBlur(radius))


# ---------- audio ----------

def theme() -> array.array:
    n = int(RATE * THEME_SECONDS)
    out = array.array("h", bytes(2 * n))
    rng = random.Random(10)
    chords = ((55.0, 82.41, 110.0), (49.0, 73.42, 98.0), (58.27, 87.31, 116.54), (41.2, 61.74, 82.41), (55.0, 82.41, 130.81))
    bells = [(t, 660.0 if i % 2 else 880.0) for i, t in enumerate(SHOT_TIMES)]
    for i in range(n):
        t = i / RATE
        shot = sum(1 for s in SHOT_TIMES if t >= s) - 1
        env = min(1.0, t / 2.0) * min(1.0, (THEME_SECONDS - t) / 2.5)
        swell = 0.75 + 0.25 * math.sin(2 * math.pi * t / 8.0)
        v = sum(math.sin(2 * math.pi * f * t + k) for k, f in enumerate(chords[shot])) * 0.13 * swell
        v += math.sin(2 * math.pi * chords[shot][0] * 0.5 * t) * 0.18  # sub
        if 21.0 <= t < 24.0:  # rising noise before the hunters
            v += (rng.random() * 2 - 1) * 0.25 * ((t - 21.0) / 3.0) ** 2
        for bt, bf in bells:
            dt = t - bt
            if 0 <= dt < 3.0:
                v += math.exp(-dt * 2.2) * (math.sin(2 * math.pi * bf * dt) * 0.25 + math.sin(2 * math.pi * bf * 2.76 * dt) * 0.08)
        out[i] = int(max(-1.0, min(1.0, v * env)) * 28000)
    return out


def boom() -> array.array:
    n = int(RATE * 2.2)
    out = array.array("h", bytes(2 * n))
    rng = random.Random(24)
    low = 0.0
    for i in range(n):
        t = i / RATE
        f = 90.0 * math.exp(-t * 3.0) + 30.0
        low = low * 0.97 + (rng.random() * 2 - 1) * 0.03
        v = math.sin(2 * math.pi * f * t) * math.exp(-t * 1.6) + low * 6.0 * math.exp(-t * 2.5)
        out[i] = int(max(-1.0, min(1.0, v * 0.9)) * 30000)
    return out


def write_wav(path: Path, samples: array.array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


def main() -> None:
    content = Path(sys.argv[1])
    img_dir = content / "panorama" / "images" / "custom_game" / "cutscene"
    img_dir.mkdir(parents=True, exist_ok=True)
    for name, fn, seed in (("rift", slide_rift, 1), ("mage", slide_mage, 2), ("hunters", slide_hunters, 3)):
        fn(random.Random(seed)).save(img_dir / f"{name}.png", optimize=True)
        print("wrote", img_dir / f"{name}.png")
    snd = content / "sounds" / "mcp_lab"
    write_wav(snd / "cutscene_theme.wav", theme())
    print("wrote", snd / "cutscene_theme.wav")
    tmp = snd / "_boom_tmp.wav"
    write_wav(tmp, boom())
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found in PATH: cannot write cutscene_boom.mp3")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(tmp), "-codec:a", "libmp3lame", "-b:a", "128k", str(snd / "cutscene_boom.mp3")], check=True)
    tmp.unlink()
    print("wrote", snd / "cutscene_boom.mp3")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rebuild BuddyBot portfolio media from the original photographed/demo files.

Source files remain untouched. This script outputs a color-balanced copy of the
real navigation GIF and a title card containing ONLY the original robot photo.
Requires ffmpeg/ffprobe and Pillow. No generated/fictional robot art is used.
"""
from pathlib import Path
import json
import shutil
import subprocess

from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "portfolio"
ORIGINAL_GIF = ASSETS / "checkpoint-navigation.gif"
OUTPUT_GIF = ASSETS / "checkpoint-navigation-polished.gif"
ORIGINAL_PHOTO = ASSETS / "buddybot-hero-v2.jpg"
OUTPUT_HERO = ASSETS / "buddybot-hero-editorial.jpg"


def cmd(args):
    print("RUN:", " ".join(map(str, args)), flush=True)
    subprocess.run([str(a) for a in args], check=True)


def glyph_font(size, bold=False):
    paths = (
        ["/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"]
    )
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSerif.ttf", size)


def polish_gif():
    assert ORIGINAL_GIF.exists(), f"Source GIF not found: {ORIGINAL_GIF}"
    assert shutil.which("ffmpeg"), "ffmpeg is required"
    print("Original animation size:", ORIGINAL_GIF.stat().st_size)
    # Mild correction only: the carpet IS reddish in the source. Do not invent
    # details, substitute frames or fake motion. Retain native dimensions/fps.
    filter_graph = (
        "[0:v]eq=contrast=1.075:brightness=0.012:saturation=0.82,"
        "colorbalance=rs=-0.025:bs=0.018,"
        "unsharp=5:5:0.50,split[a][b];"
        "[a]palettegen=max_colors=224:stats_mode=full[p];"
        "[b][p]paletteuse=dither=sierra2_4a"
    )
    cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", ORIGINAL_GIF, "-filter_complex", filter_graph,
         "-loop", "0", OUTPUT_GIF])
    assert OUTPUT_GIF.exists() and OUTPUT_GIF.stat().st_size > 1000
    print("Polished GIF bytes:", OUTPUT_GIF.stat().st_size)
    # Check that image/video can be opened, without manipulating any frames.
    with Image.open(OUTPUT_GIF) as im:
        print("Polished GIF:", im.size, "frames:", getattr(im, "n_frames", None))


def polish_hero():
    assert ORIGINAL_PHOTO.exists(), f"Source photo not found: {ORIGINAL_PHOTO}"
    base = Image.new("RGB", (1200, 430), "#101010")
    d = ImageDraw.Draw(base)
    ivory, muted = "#F2EFE8", "#BEB8AF"
    small = glyph_font(23)
    heading = glyph_font(91)
    sub = glyph_font(24)
    d.text((66, 44), "RASASOE", fill=ivory, font=small, spacing=8)
    d.text((66, 155), "BuddyBot", fill=ivory, font=heading)
    d.text((69, 274), "Home AI Serving Robot Prototype", fill=muted, font=sub)
    d.line((66, 340, 656, 340), fill="#6B6763", width=1)
    d.text((68, 361), "ROS 2    /    LiDAR    /    Vision    /    Voice", fill=muted, font=glyph_font(17))
    with Image.open(ORIGINAL_PHOTO) as source:
        photo = ImageOps.exif_transpose(source).convert("RGB")
        photo = ImageEnhance.Color(photo).enhance(0.77)
        photo = ImageEnhance.Contrast(photo).enhance(1.08)
        photo = ImageEnhance.Sharpness(photo).enhance(1.12)
        contained = ImageOps.contain(photo, (430, 358), Image.Resampling.LANCZOS)
        x = 730 + (430 - contained.width) // 2
        y = 36 + (358 - contained.height) // 2
        base.paste(contained, (x, y))
        d = ImageDraw.Draw(base)
        d.rectangle([x - 1, y - 1, x + contained.width, y + contained.height],
                    outline="#645F59", width=1)
    base.save(OUTPUT_HERO, "JPEG", quality=94, subsampling=0, optimize=True)
    print("Actual-photo title card:", OUTPUT_HERO, OUTPUT_HERO.stat().st_size)


def update_readmes():
    # Do not point README at files that have not been produced.
    assert OUTPUT_GIF.exists() and OUTPUT_HERO.exists()
    kr = ROOT / "README.md"
    en = ROOT / "README.en.md"
    x = kr.read_text(encoding="utf-8")
    x = x.replace(
        '<img src="docs/assets/portfolio/buddybot-hero-v2.jpg" width="370"',
        '<img src="docs/assets/portfolio/buddybot-hero-editorial.jpg" width="100%"')
    x = x.replace(
        '<img src="docs/assets/portfolio/checkpoint-navigation.gif" width="560"',
        '<img src="docs/assets/portfolio/checkpoint-navigation-polished.gif" width="560"')
    x = x.replace(
        '[원본 주행 GIF 열기](docs/assets/portfolio/checkpoint-navigation.gif)',
        '[원본 주행 GIF](docs/assets/portfolio/checkpoint-navigation.gif) · '
        '[색감 보정본](docs/assets/portfolio/checkpoint-navigation-polished.gif)')
    kr.write_text(x, encoding="utf-8")
    y = en.read_text(encoding="utf-8")
    y = y.replace(
        'docs/assets/portfolio/buddybot-hero-v2.jpg',
        'docs/assets/portfolio/buddybot-hero-editorial.jpg')
    en.write_text(y, encoding="utf-8")


if __name__ == "__main__":
    polish_gif()
    polish_hero()
    update_readmes()

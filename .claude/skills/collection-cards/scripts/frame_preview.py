#!/usr/bin/env python3
"""Preview a set inside a simplified set-window frame: rarity stars over the top
edge, "+2" badges, the name plate under the art. Use it in QA to see whether
objects collide with the stars/badge (as on the Miro set templates).

Geometry (share of the card art, measured on the Miro template):
  stars: ~14% of art height each, row centered, overlapping the top edge by ~6%;
  "+2" badge: x -12%..33%, y 15%..41% (only on the slots given in --badges);
  name plate: directly below the art, ~22% of art height.

Usage: python3 frame_preview.py output/<theme>/<variant> [--badges 2 4 7]
Writes <variant>/_frame_preview.png. Requires Pillow.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ART_W, ART_H = 300, 335
PAD, BORDER = 34, 10
ORANGE, ORANGE_D, FRAME, STAR, STAR_D = (233, 106, 20), (196, 74, 10), (196, 205, 245), (255, 214, 40), (230, 140, 20)


def font(size):
    for path in ("/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def star(d, cx, cy, r):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.48
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=STAR, outline=STAR_D, width=3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("variant_dir")
    p.add_argument("--badges", nargs="*", type=int, default=[2, 4, 7])
    a = p.parse_args()
    vdir = Path(a.variant_dir)
    plan = json.loads((vdir / "set.json").read_text(encoding="utf-8"))
    cards = {c["slot"]: c for c in plan["cards"]}

    plate_h = int(ART_H * 0.22)
    cw, ch = ART_W + 2 * BORDER, ART_H + plate_h + 2 * BORDER
    W = 5 * cw + 6 * PAD
    H = 2 * ch + 3 * PAD + 60 + 40
    sheet = Image.new("RGB", (W, H), ORANGE)
    d = ImageDraw.Draw(sheet)
    d.text((W // 2, 40), plan.get("set_name", "").upper(), fill=(255, 225, 90), font=font(40), anchor="mm")
    f_lab = font(22)
    for slot in range(1, 11):
        col, row = (slot - 1) % 5, (slot - 1) // 5
        x = PAD + col * (cw + PAD)
        y = 80 + PAD + row * (ch + PAD + 20)
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=22, fill=FRAME)
        files = sorted(f for f in vdir.glob(f"{slot:02d}_*_430x480.png"))
        if files:
            art = Image.open(files[0]).convert("RGB").resize((ART_W, ART_H), Image.LANCZOS)
            sheet.paste(art, (x + BORDER, y + BORDER))
        py = y + BORDER + ART_H
        d.rounded_rectangle((x + BORDER, py, x + BORDER + ART_W, py + plate_h), radius=14, fill=ORANGE_D)
        c = cards.get(slot, {})
        d.text((x + cw // 2, py + plate_h // 2), c.get("label", "").upper(), fill="white", font=f_lab, anchor="mm")
        n = int(c.get("rarity", 1))
        r = ART_H * 0.07
        cy = y + BORDER + ART_H * 0.06 - r
        for i in range(n):
            star(d, x + cw / 2 + (i - (n - 1) / 2) * r * 1.9, cy, r)
        if slot in a.badges:
            bx0, by0 = x + BORDER - ART_W * 0.12, y + BORDER + ART_H * 0.15
            bx1, by1 = x + BORDER + ART_W * 0.33, y + BORDER + ART_H * 0.41
            bh = by1 - by0
            d.rounded_rectangle((bx0, by0 + bh * 0.22, bx1, by1 - bh * 0.22), radius=10, fill=STAR, outline=STAR_D, width=3)
            d.text(((bx0 + bx1) / 2, (by0 + by1) / 2), "+2", fill=(110, 60, 10), font=font(28), anchor="mm")
    out = vdir / "_frame_preview.png"
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Make a 5x2 PNG overview of a set variant for visual QA (and for Miro).

Usage: python3 qa_sheet.py output/<theme>/<variant> [--cell 300]
Uses the 430x480 game copies (NN_*_430x480.png). Writes <variant>/_sheet.png
with slot number, rarity and label under each card. Requires Pillow.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for path in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf","/System/Library/Fonts/Helvetica.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("variant_dir")
    p.add_argument("--cell", type=int, default=300)
    a = p.parse_args()
    vdir = Path(a.variant_dir)
    plan = json.loads((vdir / "set.json").read_text(encoding="utf-8"))
    cards = {c["slot"]: c for c in plan["cards"]}
    w, h = a.cell, int(a.cell * 480 / 430)
    pad, cap = 12, 44
    sheet = Image.new("RGB", (5 * (w + pad) + pad, 2 * (h + cap + pad) + pad + 50), (29, 27, 46))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), f"{plan.get('variant', '')} — {plan.get('set_name', '')}", fill=(244, 241, 255), font=font(28))
    for slot in range(1, 11):
        files = sorted(vdir.glob(f"{slot:02d}_*_430x480.png"))
        x = pad + (slot - 1) % 5 * (w + pad)
        y = 50 + pad + (slot - 1) // 5 * (h + cap + pad)
        if files:
            sheet.paste(Image.open(files[0]).convert("RGB").resize((w, h), Image.LANCZOS), (x, y))
        c = cards.get(slot, {})
        d.text((x, y + h + 4), f"{slot}  {'★' * c.get('rarity', 0)}", fill=(255, 210, 63), font=font(16))
        d.text((x, y + h + 22), f"{c.get('label', '')}  · cat {c.get('category', '?')}", fill=(244, 241, 255), font=font(16))
    out = vdir / "_sheet.png"
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()

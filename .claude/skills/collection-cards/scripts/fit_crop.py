#!/usr/bin/env python3
"""Place the object in the card frame's SAFE ZONE (successor of center_crop.py).

In the set window the card art is shown in full, the name plate sits BELOW it,
but the rarity stars overlap the top edge (~6%) and a "+N" badge can cover the
upper-left corner. Game cards therefore keep more air above the object than
below it (measured on 22 cards of categories 1-3: top ~11-17%, bottom ~10-13%).

Given a generated image with spare background on all sides and its cut-out,
this script chooses a 9:10 window (scaled to 900x1000) so that:
  * the object is horizontally centered,
  * its margins match the category targets below (object as large as allowed),
  * the window never upscales (min 900x1000 px) and stays inside the image.

Usage:
  python3 fit_crop.py --image ext.png --cutout cut.png --out card.png --category 2 [--game-size 430x480]
Prints JSON: margins after (% of card), window, scale, flags. needs_regen=true if
the object could not fit: top margin < 80% of the target (stars!) or another margin < half of it.
"""
import argparse
import json

from PIL import Image

# target margins as share of the final card: top, bottom, left/right
# (negative = may be cropped by the frame edge, used for environments)
TARGETS = {
    1: (0.16, 0.12, 0.08),
    2: (0.14, 0.10, 0.08),
    3: (0.13, 0.07, 0.04),
    4: (0.12, -0.03, -0.04),
}
ASPECT = 0.9  # width / height
MIN_H = 1000


def bbox(cut_path, size):
    cut = Image.open(cut_path).convert("RGBA")
    if cut.size != size:
        cut = cut.resize(size, Image.LANCZOS)
    return cut.getchannel("A").point(lambda v: 255 if v >= 128 else 0).getbbox()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--cutout", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--category", type=int, required=True, choices=[1, 2, 3, 4])
    p.add_argument("--width", type=int, default=900)
    p.add_argument("--height", type=int, default=1000)
    p.add_argument("--game-size", default="")
    p.add_argument("--center", choices=["bbox", "mass"], default="bbox",
                   help="horizontal centering: bbox = middle of the bounding box; mass = centroid of the object "
                        "(better for asymmetric shapes, e.g. a hand with fingers spread to one side)")
    p.add_argument("--margins", default="", help="manual override 'top,bottom,side' as shares, e.g. 0.12,0.25,0.02 "
                   "(when the cut-out misses part of the scene, e.g. a UFO's light beam)")
    a = p.parse_args()

    img = Image.open(a.image).convert("RGB")
    W, H = img.size
    bb = bbox(a.cutout, (W, H))
    if bb is None:
        print(json.dumps({"needs_regen": True, "reason": "no object in cutout"}))
        return
    l, t, r, b = bb
    ow, oh = r - l, b - t
    mt, mb, ms = (float(v) for v in a.margins.split(",")) if a.margins else TARGETS[a.category]

    # smallest window that respects the margins (object as big as allowed)
    h_need = max(oh / (1 - mt - mb), ow / (1 - 2 * ms) / ASPECT, MIN_H)
    h_max = min(H, W / ASPECT)
    clamped = h_need > h_max
    h = min(h_need, h_max)
    w = h * ASPECT

    cx = (l + r) / 2
    if a.center == "mass":
        cut = Image.open(a.cutout).convert("RGBA")
        if cut.size != (W, H):
            cut = cut.resize((W, H))
        al = cut.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        cols = [sum(1 for v in al.crop((x, 0, x + 1, H)).getdata() if v) for x in range(0, W, 4)]
        tot = sum(cols)
        if tot:
            cx = sum(i * 4 * c for i, c in enumerate(cols)) / tot
    x0 = cx - w / 2
    free = h - oh
    top = free * mt / (mt + mb) if (mt + mb) > 0 else mt * h
    y0 = t - top
    x0 = max(0, min(x0, W - w))
    y0 = max(0, min(y0, H - h))

    card = img.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize((a.width, a.height), Image.LANCZOS)
    card.save(a.out)
    if a.game_size:
        gw, gh = (int(v) for v in a.game_size.lower().split("x"))
        card.resize((gw, gh), Image.LANCZOS).save(a.out.replace(".png", f"_{gw}x{gh}.png"))

    after = {"top": round((t - y0) / h * 100, 1), "bottom": round((y0 + h - b) / h * 100, 1),
             "left": round((l - x0) / w * 100, 1), "right": round((x0 + w - r) / w * 100, 1)}
    # the top is critical: rarity stars cover it (a mast or a rocket nose must stay below them)
    short = [k for k, tgt in (("top", mt), ("bottom", mb), ("left", ms), ("right", ms))
             if tgt > 0 and after[k] < tgt * 100 * (0.8 if k == "top" else 0.5)]
    print(json.dumps({"source_size": [W, H], "object_bbox": bb, "window": [round(x0), round(y0), round(w), round(h)],
                      "scale": round(h / a.height, 3), "margins_pct": after,
                      "target_pct": {"top": mt * 100, "bottom": mb * 100, "sides": ms * 100},
                      "clamped": clamped, "needs_regen": bool(short),
                      "reason": ("margins too small: " + ", ".join(short)) if short else ""}))


if __name__ == "__main__":
    main()

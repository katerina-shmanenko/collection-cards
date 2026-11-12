#!/usr/bin/env python3
"""LEGACY (horizontal only) — use fit_crop.py, which also handles vertical safe zone.

Auto-centering: crop a card-sized window centered on the object.

Cards are generated slightly WIDER than the final size (e.g. 1100x1000 for a
900x1000 card). A background-removed cut-out (alpha PNG from Magnific
images_remove_background) tells us where the object is; we then crop the final
window so the object's bounding box has equal left/right margins.

Usage:
  python3 center_crop.py --image gen.png --cutout cutout.png --out card.png \
      [--width 900 --height 1000] [--game-size 430x480]

Prints a JSON report: margins before/after (in % of final width), shift applied,
and "needs_regen": true if the object could not be centered within the
available safety margin (or is too big / touches the edges).
Requires Pillow.
"""
import argparse
import json
import sys

from PIL import Image

ALPHA_THRESHOLD = 128
MAX_IMBALANCE = 0.04  # residual |left-right| margin difference allowed, share of final width


def object_bbox(cutout_path, target_size):
    cut = Image.open(cutout_path).convert("RGBA")
    if cut.size != target_size:
        cut = cut.resize(target_size, Image.LANCZOS)
    alpha = cut.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0)
    return alpha.getbbox()  # (left, top, right, bottom) or None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--cutout", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--width", type=int, default=900)
    p.add_argument("--height", type=int, default=1000)
    p.add_argument("--game-size", default="", help="also save a WxH game-size copy, e.g. 430x480")
    p.add_argument("--allow-crop", action="store_true",
                   help="category 4 environments: the object may be cropped by the frame, so 'too wide' is not a defect")
    a = p.parse_args()

    img = Image.open(a.image).convert("RGB")
    W, H = img.size
    if W < a.width or H < a.height:
        sys.exit(f"image {W}x{H} is smaller than target {a.width}x{a.height}")

    bbox = object_bbox(a.cutout, (W, H))
    if bbox is None:
        print(json.dumps({"needs_regen": True, "reason": "no object found in cutout"}))
        return
    left, top, right, bottom = bbox
    cx = (left + right) / 2

    # Window centered on the object, clamped to the image.
    x0 = round(cx - a.width / 2)
    clamped = False
    if x0 < 0:
        x0, clamped = 0, True
    if x0 + a.width > W:
        x0, clamped = W - a.width, True
    y0 = max(0, (H - a.height) // 2)

    def margins(win_x0):
        l = (left - win_x0) / a.width
        r = (win_x0 + a.width - right) / a.width
        return round(l * 100, 1), round(r * 100, 1)

    naive_x0 = (W - a.width) // 2  # what a plain center crop would give
    before = margins(naive_x0)
    after = margins(x0)
    imbalance = abs(after[0] - after[1]) / 100
    too_wide = (right - left) > a.width * 0.95 and not a.allow_crop
    if a.allow_crop:
        imbalance = 0.0  # environment cards: centering on the main part is best-effort

    card = img.crop((x0, y0, x0 + a.width, y0 + a.height))
    card.save(a.out)
    if a.game_size:
        gw, gh = (int(v) for v in a.game_size.lower().split("x"))
        card.resize((gw, gh), Image.LANCZOS).save(a.out.replace(".png", f"_{gw}x{gh}.png"))

    print(json.dumps({
        "source_size": [W, H],
        "object_bbox": bbox,
        "margins_plain_center_crop_pct": {"left": before[0], "right": before[1]},
        "margins_after_pct": {"left": after[0], "right": after[1]},
        "shift_px": x0 - naive_x0,
        "clamped": clamped,
        "needs_regen": bool(imbalance > MAX_IMBALANCE or too_wide),
        "reason": "object too wide" if too_wide else ("not enough margin to center" if imbalance > MAX_IMBALANCE else ""),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

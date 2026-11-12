#!/usr/bin/env python3
"""Remove a halo of the OLD background around a pasted object (local, free).

After a background edit/extension the object is pasted back from the original
picture; if the paste mask was a bit wide, a thin rim of the old background
(e.g. blue sky around a rover on a new Martian sky) stays around the object.
This script finds the object (isnet cut-out), takes a ring just outside its
edge and refills it from the surrounding NEW background (normalized blur),
leaving the object itself untouched.

Usage: python3 defringe.py --image edit.png --out fixed.png [--ring 12]
Requires Pillow, numpy, rembg.
"""
import argparse

import numpy as np
from PIL import Image, ImageFilter
from rembg import new_session, remove


def box(arr, r):
    """box blur along both axes with cumulative sums (edge-padded)."""
    for ax in (0, 1):
        pad = [(0, 0)] * arr.ndim
        pad[ax] = (r + 1, r)
        c = np.cumsum(np.pad(arr, pad, mode="edge"), axis=ax)
        hi = np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax)
        lo = np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)
        arr = (hi - lo) / (2 * r + 1)
    return arr


def blur(arr, r):
    for _ in range(3):  # three box passes ~ gaussian
        arr = box(arr, r)
    return arr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ring", type=int, default=12, help="ring width outside the object to refill, px")
    p.add_argument("--shrink", type=int, default=2, help="also refill this many px inside the object edge")
    p.add_argument("--fringe-color", choices=["blue", "any"], default="any",
                   help="blue: refill only bluish pixels in a band around the object edge (old blue sky halo on a warm new sky)")
    p.add_argument("--band", type=int, default=14, help="band width inside the object edge for --fringe-color")
    p.add_argument("--mask-from", default="",
                   help="take the object mask from this image (the ORIGINAL, same size) — recommended: on the edited "
                        "image the cut-out tends to include the halo itself")
    a = p.parse_args()

    img = Image.open(a.image).convert("RGB")
    src = Image.open(a.mask_from).convert("RGB") if a.mask_from else img
    alpha = remove(src, session=new_session("isnet-general-use")).getchannel("A")
    obj = alpha.point(lambda v: 255 if v >= 128 else 0)
    core = obj.filter(ImageFilter.MinFilter(2 * a.shrink + 1)) if a.shrink else obj
    zone = obj.filter(ImageFilter.MaxFilter(2 * a.ring + 1))

    im = np.asarray(img).astype(np.float32)
    valid = (np.asarray(zone) == 0).astype(np.float32)
    r = max(2, int(a.ring * 0.8))
    num = blur(im * valid[..., None], r)
    den = blur(valid[..., None], r)
    fill = num / np.maximum(den, 1e-3)

    keep = np.asarray(core.filter(ImageFilter.GaussianBlur(1))).astype(np.float32)[..., None] / 255
    inzone = (np.asarray(zone) > 0)[..., None]
    if a.fringe_color == "blue":
        inner = np.asarray(obj.filter(ImageFilter.MinFilter(2 * a.band + 1))) > 0
        band = (np.asarray(zone) > 0) & ~inner
        R, G, B = im[..., 0], im[..., 1], im[..., 2]
        bluish = band & (B > R + 8) & (B > G - 10)
        bmask = Image.fromarray((bluish * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
        w = np.asarray(bmask).astype(np.float32)[..., None] / 255
        out = im * (1 - w) + fill * w
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(a.out)
        print(a.out)
        return
    out = np.where(inzone, im * keep + fill * (1 - keep), im)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()

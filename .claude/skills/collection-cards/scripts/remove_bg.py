#!/usr/bin/env python3
"""Local background removal (free alternative to Magnific images_remove_background).

Produces an RGBA cut-out used only to find the object's bounding box for
fit_crop.py. Requires: python3 -m pip install --user "rembg[cpu]"
(first run downloads the isnet-general-use model, ~180 MB, into ~/.u2net).
isnet is used instead of the default u2net: u2net dropped a blue ribbon on an amber
background and kept only its gold center, which broke auto-centering.

Usage: python3 remove_bg.py --image gen.png --out cutout.png
"""
import argparse

from PIL import Image
from rembg import new_session, remove


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="isnet-general-use")
    a = p.parse_args()
    remove(Image.open(a.image), session=new_session(a.model)).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()

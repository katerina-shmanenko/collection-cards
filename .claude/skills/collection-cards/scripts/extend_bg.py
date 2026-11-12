#!/usr/bin/env python3
"""Extend a card's background outward (outpainting) without changing the object.

Used when a card is already approved but the object sits too close to an edge
(e.g. touches the stars at the top): we enlarge the canvas, let the model paint
only the new border, then paste the original pixels back on top with a soft
edge, so the approved art stays exactly as it was. After that fit_crop.py can
place the object in the frame's safe zone.

Usage:
  python3 extend_bg.py --image gen.png --out ext.png [--pad-x 160 --pad-y 176] [--hint "soft sky blue wall"]
Default pads turn 1104x1008 into 1424x1360 (both divisible by 16).
How: the border is pre-filled with a blurred stretch of the picture, the model
repaints the whole canvas, and the original pixels are pasted back over the
center (soft 40 px blend). A transparent border or a mask produced dark/black
edges in tests, so by default no mask is sent.
Cost: one OpenAI image edit (~$0.07). Needs OPENAI_API_KEY (see openai_generate.py).
"""
import argparse
import base64
import io
import json
import os
import sys
import tempfile

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openai_generate import API_URL, call, load_key, multipart  # noqa: E402

PROMPT = ("This is a finished collectible card illustration placed in the middle of a larger canvas; "
          "the blurry border around it is a rough placeholder. Repaint ONLY that border by seamlessly continuing the "
          "existing background outward exactly as it is, as bright and evenly lit as the center: same colors, gradient, pattern, wall, floor, ground, "
          "sky, clouds and lighting{hint}. No dark edges, no vignette, no darkening toward the corners. Do not add any new objects, props, text or frames. Do not change, "
          "move, resize or redraw the central illustration. Same soft stylized 3D render style.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--pad-x", type=int, default=160)
    p.add_argument("--pad-y", type=int, default=176)
    p.add_argument("--hint", default="")
    p.add_argument("--edit", default="",
                   help="background edit instead of extension, e.g. 'remove the clouds and make the sky a bit darker'. "
                        "Use with --pad-x 0 --pad-y 0 --paste object: the model repaints the background, the object is kept")
    p.add_argument("--model", default="gpt-image-2.6-sunburst")
    p.add_argument("--quality", default="medium")
    p.add_argument("--feather", type=int, default=40, help="soft blend width (px) at the edge of the original")
    p.add_argument("--mask", action="store_true",
                   help="also send a mask (not recommended: with gpt-image-2.6 the masked border came back black)")
    p.add_argument("--paste", choices=["full", "object"], default="full",
                   help="what to paste back from the original: the whole picture (scenes, cat. 3-4) or only the "
                        "object by its cut-out (plain backgrounds, cat. 1-2: avoids a visible square seam)")
    p.add_argument("--save-raw", action="store_true", help="(always on) the raw model output is saved as <out>_raw.png")
    p.add_argument("--prefill-out", default="",
                   help="magnific route: only save the pre-filled canvas here (upload it, run images_generate with it as an "
                        "image reference and the printed prompt, download the result to <out>_raw.png, then rerun with --reuse-raw)")
    p.add_argument("--reuse-raw", action="store_true", help="do not call the API: re-composite from an existing <out>_raw.png")
    a = p.parse_args()

    src = Image.open(a.image).convert("RGBA")
    W, H = src.size
    W2, H2 = W + 2 * a.pad_x, H + 2 * a.pad_y
    if (W2 % 16 or H2 % 16) and not (a.pad_x == 0 and a.pad_y == 0):
        sys.exit(f"extended size {W2}x{H2} must be divisible by 16")
    # Rough pre-fill of the border: the picture stretched to the new size and blurred,
    # so the model continues real colors (an empty/transparent border came back as a dark vignette).
    prefill = src.convert("RGB").resize((W2, H2), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    prefill.paste(src.convert("RGB"), (a.pad_x, a.pad_y))
    mask = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    mask.paste(Image.new("RGBA", (W, H), (0, 0, 0, 255)), (a.pad_x, a.pad_y))

    if a.prefill_out:
        prefill.save(a.prefill_out)
        hint = f" ({a.hint})" if a.hint else ""
        print(json.dumps({"prefill": a.prefill_out, "size": [W2, H2], "raw_expected": a.out.replace(".png", "_raw.png"),
                          "prompt": PROMPT.format(hint=hint)}))
        return
    tmp = tempfile.mkdtemp()
    img_path, mask_path = os.path.join(tmp, "image.png"), os.path.join(tmp, "mask.png")
    prefill.save(img_path)
    mask.save(mask_path)  # transparent border = area to repaint, opaque center = keep

    hint = f" ({a.hint})" if a.hint else ""
    prompt = PROMPT.format(hint=hint)
    if a.edit:
        prompt = ("Edit this collectible card illustration: change ONLY the background as follows: " + a.edit +
                  ". Keep the main object exactly the same shape, colors, position and size. Same soft stylized 3D "
                  "render style, bright and saturated, no vignette, no text.")
    fields = [("model", a.model), ("prompt", prompt), ("size", f"{W2}x{H2}"),
              ("quality", a.quality), ("n", "1"), ("output_format", "png")]
    files = [("image[]", img_path)] + ([("mask", mask_path)] if a.mask else [])
    raw_path = a.out.replace(".png", "_raw.png")
    if a.reuse_raw:
        out, resp = Image.open(raw_path).convert("RGB"), {}
    else:
        body, ctype = multipart(fields, files)
        resp = call(API_URL, body, ctype, load_key())
        out = Image.open(io.BytesIO(base64.b64decode(resp["data"][0]["b64_json"]))).convert("RGB")
        out.save(raw_path)
    if out.size != (W2, H2):
        out = out.resize((W2, H2), Image.LANCZOS)

    # Paste the approved original back.
    f = a.feather
    m = Image.new("L", (W2, H2), 0)
    if a.paste == "object":
        # only the object (cut-out, slightly grown and softened): the whole background comes from the model
        from rembg import new_session, remove
        alpha = remove(src.convert("RGB"), session=new_session("isnet-general-use")).getchannel("A")
        # tight mask: a wide one carried a halo of the OLD background around the object (blue rim on the rover)
        alpha = alpha.point(lambda v: 255 if v >= 128 else 0).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
        m.paste(alpha, (a.pad_x, a.pad_y))
    else:
        # whole picture, blending only a thin band at its edge
        m.paste(255, (a.pad_x + f, a.pad_y + f, a.pad_x + W - f, a.pad_y + H - f))
        m = m.filter(ImageFilter.GaussianBlur(f / 2))
    full_src = Image.new("RGB", (W2, H2))
    full_src.paste(src.convert("RGB"), (a.pad_x, a.pad_y))
    Image.composite(full_src, out, m).save(a.out)
    print(json.dumps({"saved": a.out, "size": [W2, H2], "pad": [a.pad_x, a.pad_y], "usage": resp.get("usage")}))


if __name__ == "__main__":
    main()

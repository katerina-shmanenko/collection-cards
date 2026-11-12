#!/usr/bin/env python3
"""Generate one card image with an in-house model + style LoRA behind ComfyUI.

Template adapter: lets generate_set.py use a studio's own model instead of OpenAI / Magnific
(`generate_set.py ... --generator lora`). The rest of the pipeline (plan check, cut-out,
safe-zone fit, QA, preview) does not change. Only the Python stdlib is used.

Contract (same as openai_generate.py):
  python3 lora_generate.py --prompt-file prompt.txt --category 1 --out gen.png [--n 2] [--quality medium]
  stdout: JSON {"saved": [...], "usage": null, ...}

Setup (environment variables or the project's .env):
  LORA_API_URL    ComfyUI server, e.g. http://comfy.internal:8188
  LORA_WORKFLOW   workflow exported from ComfyUI with "Save (API Format)" (.json); put placeholders
                  into its text/number fields:
                    "%PROMPT%" "%NEGATIVE%" "%SEED%" "%WIDTH%" "%HEIGHT%" "%BATCH%" "%STEPS%" "%CATEGORY%"
                  (the LoRA itself is chosen inside the workflow, LoraLoader node)
  LORA_TRIGGER    optional trigger word of the LoRA, put in front of the prompt
  LORA_STYLE_TEXT keep | drop (default drop): with a style LoRA the long style block of the
                  prompt (rendering, light, colors) is redundant; "drop" keeps the mood and
                  everything from "Subject:" on — the object, background, camera and bans.

Notes:
  - Style references (image[] in OpenAI) are not sent: the LoRA holds the style. If the workflow
    has an IP-Adapter, load category references there.
  - Background extension (extend_bg.py) still uses OpenAI; for a fully in-house setup replace it
    with an outpainting workflow of the same model.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))
STEPS = {"low": 20, "medium": 30, "high": 45}
NEGATIVE = ("text, letters, numbers, logo, watermark, frame, border, card UI, rating stars, particles, "
            "sparkles, vignette, photorealistic, flat 2D, outlines, dark, moody, fog")


def setting(name, default=None):
    val = os.environ.get(name, "").strip()
    env = os.path.join(PROJECT_DIR, ".env")
    if not val and os.path.exists(env):
        with open(env) as f:
            for line in f:
                if line.strip().startswith(name + "="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
    return val or default


def shorten(prompt):
    """Drop the style block (the LoRA holds the style); keep mood + subject + camera + bans."""
    m = re.search(r"\b(Mood:|Subject:)", prompt)
    return prompt[m.start():] if m else prompt


def fill(node, values):
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        if node in values:  # whole-field placeholder keeps its type (numbers stay numbers)
            return values[node]
        for k, v in values.items():
            node = node.replace(k, str(v))
    return node


def http(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body if url.split("?")[0].endswith("/view") else json.loads(body)


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    p.add_argument("--category", type=int, choices=[1, 2, 3, 4])
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--quality", default="medium", choices=list(STEPS))
    p.add_argument("--size", default="1248x1248")
    p.add_argument("--refs", nargs="*", help="ignored: the LoRA holds the style")
    p.add_argument("--timeout", type=int, default=600)
    a = p.parse_args()

    url, wf_path = setting("LORA_API_URL"), setting("LORA_WORKFLOW")
    if not url or not wf_path:
        sys.exit("LoRA generator is not configured: set LORA_API_URL (ComfyUI server) and LORA_WORKFLOW "
                 "(workflow .json in API format with %PROMPT% etc.) in .env — see the header of lora_generate.py")
    prompt = a.prompt if a.prompt else open(a.prompt_file).read().strip()
    if setting("LORA_STYLE_TEXT", "drop") == "drop":
        prompt = shorten(prompt)
    if setting("LORA_TRIGGER"):
        prompt = f"{setting('LORA_TRIGGER')}, {prompt}"
    w, h = (int(x) for x in a.size.lower().split("x"))
    values = {"%PROMPT%": prompt, "%NEGATIVE%": NEGATIVE, "%SEED%": random.randint(0, 2**31 - 1),
              "%WIDTH%": w, "%HEIGHT%": h, "%BATCH%": a.n, "%STEPS%": STEPS[a.quality],
              "%CATEGORY%": a.category or 0}
    with open(os.path.join(PROJECT_DIR, wf_path) if not os.path.isabs(wf_path) else wf_path) as f:
        workflow = fill(json.load(f), values)

    t0 = time.time()
    base = url.rstrip("/")
    pid = http(f"{base}/prompt", {"prompt": workflow, "client_id": "collection-cards"})["prompt_id"]
    while True:  # ComfyUI queues the job; poll its history until the images are there
        hist = http(f"{base}/history/{pid}")
        if pid in hist and hist[pid].get("outputs"):
            break
        if time.time() - t0 > a.timeout:
            sys.exit(f"ComfyUI did not finish in {a.timeout}s (prompt_id {pid})")
        time.sleep(2)
    images = [img for out in hist[pid]["outputs"].values() for img in out.get("images", [])
              if img.get("type", "output") == "output"]
    if not images:
        sys.exit("ComfyUI returned no images: check that the workflow ends with a SaveImage node")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    stem, ext = os.path.splitext(a.out)
    saved = []
    for i, img in enumerate(images[:a.n]):
        q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output")})
        path = a.out if i == 0 else f"{stem}_{i + 1}{ext or '.png'}"
        with open(path, "wb") as f:
            f.write(http(f"{base}/view?{q}"))
        saved.append(path)
    print(json.dumps({"saved": saved, "model": "comfyui+lora", "size": a.size, "quality": a.quality,
                      "usage": None, "seconds": round(time.time() - t0, 1)}, indent=2))


if __name__ == "__main__":
    main()

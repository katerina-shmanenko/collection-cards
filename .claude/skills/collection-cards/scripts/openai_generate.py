#!/usr/bin/env python3
"""Generate one card image with the OpenAI Images API (direct alternative to Magnific MCP).

Style references are passed as input images to /v1/images/edits, so the model
copies the rendering style of real game cards. Only the Python stdlib is used.

The API key is read from the OPENAI_API_KEY environment variable or from a
.env file in the project root (never pass it on the command line).

Usage:
  python3 openai_generate.py --prompt-file prompt.txt --category 1 --out gen.png
  python3 openai_generate.py --prompt "..." --refs a.png b.png --out gen.png --n 2

Options:
  --category 1..4   take 3 style references of that category from references_local.json
  --refs ...        explicit reference image paths (override --category)
  --model           gpt-image-2.6-sunburst (default, detailed) | gpt-image-2.6-flare (faster)
  --size            WxH, both divisible by 16 (default 1248x1248: spare background on all sides for fit_crop.py)
  --quality         low | medium (default) | high
  --n               number of candidates (each saved as <out>, <out>_2.png, ...)

Prints a JSON report: saved files, token usage, size, model.
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))
API_URL = "https://api.openai.com/v1/images/edits"
API_URL_NO_REFS = "https://api.openai.com/v1/images/generations"


def load_key():
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("OPENAI_API_KEY not found: copy .env.example to .env in the project root and put your key there.")
    return key


def refs_for_category(cat):
    """Original game cards (references_local.json) if present; otherwise our own approved
    cards (references_fallback.json) — the public repo ships without Playrix materials."""
    for name in ("references_local.json", "references_fallback.json"):
        with open(os.path.join(SKILL_DIR, name)) as f:
            paths = [os.path.join(PROJECT_DIR, p) for p in json.load(f)[str(cat)]]
        if all(os.path.exists(p) for p in paths):
            if name != "references_local.json":
                print("note: original game references not found, using fallback_refs (our approved cards)", file=sys.stderr)
            return paths
    sys.exit("no style references found: put game cards into references/cards_hq/ (see references_local.json)")


def multipart(fields, files):
    boundary = "----cards" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields:
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    for name, path in files:
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def call(url, body, ctype, key, retries=5):
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:1000]
            if e.code in (429, 500, 502, 503) and attempt < retries:
                time.sleep(20 * (attempt + 1))
                continue
            sys.exit(f"OpenAI API error {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # network hiccup / read timeout
            if attempt < 2:
                time.sleep(10)
                continue
            sys.exit(f"network error talking to OpenAI: {e}")


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    p.add_argument("--category", type=int, choices=[1, 2, 3, 4])
    p.add_argument("--refs", nargs="*", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="gpt-image-2.6-sunburst")
    p.add_argument("--size", default="1248x1248")
    p.add_argument("--quality", default="medium")
    p.add_argument("--n", type=int, default=1)
    a = p.parse_args()

    prompt = a.prompt if a.prompt else open(a.prompt_file).read().strip()
    w, h = (int(x) for x in a.size.lower().split("x"))
    if w % 16 or h % 16:
        sys.exit(f"size {a.size}: width and height must be divisible by 16")

    refs = a.refs if a.refs is not None else (refs_for_category(a.category) if a.category else [])
    for r in refs:
        if not os.path.exists(r):
            sys.exit(f"reference not found: {r}")

    key = load_key()
    fields = [("model", a.model), ("prompt", prompt), ("size", a.size),
              ("quality", a.quality), ("n", str(a.n)), ("output_format", "png")]
    t0 = time.time()
    if refs:
        body, ctype = multipart(fields, [("image[]", r) for r in refs])
        resp = call(API_URL, body, ctype, key)
    else:
        body = json.dumps(dict(fields, n=a.n)).encode()
        resp = call(API_URL_NO_REFS, body, "application/json", key)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    base, ext = os.path.splitext(a.out)
    saved = []
    for i, item in enumerate(resp.get("data", [])):
        path = a.out if i == 0 else f"{base}_{i + 1}{ext or '.png'}"
        with open(path, "wb") as f:
            f.write(base64.b64decode(item["b64_json"]))
        saved.append(path)

    print(json.dumps({"saved": saved, "model": a.model, "size": resp.get("size", a.size),
                      "quality": resp.get("quality", a.quality), "refs": [os.path.basename(r) for r in refs],
                      "usage": resp.get("usage"), "seconds": round(time.time() - t0, 1)}, indent=2))


if __name__ == "__main__":
    main()

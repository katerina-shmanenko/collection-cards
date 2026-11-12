#!/usr/bin/env python3
"""Run the whole pipeline for one set variant: prompts -> generation -> cut-out -> auto-centering.

Usage:
  python3 generate_set.py output/<theme>/<variant> [--slots 3 7] [--n 2] [--jobs 4] [--generator openai|lora|<script.py>]

The generator is a swappable step (--generator). Any script with the same contract works:
  args:   --prompt-file F --category 1..4 --out OUT.png --n N --quality low|medium|high
  stdout: JSON {"saved": [OUT.png, OUT_2.png, ...], "usage": ...}
Built in: openai (openai_generate.py, default) and lora (lora_generate.py, a template for an
in-house model with a style LoRA, e.g. behind ComfyUI). Everything else stays the same.

Steps per slot (in parallel, --jobs at a time; new OpenAI accounts have low rate limits):
  1. build_prompts.py set.json         -> _work/NN_prompt.txt (skipped if --keep-prompts and the file exists)
  2. <generator>_generate.py           -> _work/NN_gen.png (+ _work/NN_gen_2.png with --n 2)
  3. remove_bg.py                      -> _work/NN_cutout.png
  4. fit_crop.py                       -> NN_<label>.png (900x1000) + NN_<label>_430x480.png
                                          (object placed in the frame's safe zone, see art_style.md D)
With --n 2 every candidate is centered; the first goes to NN_<label>.png, the rest to _alt/.
If the object misses the safe zone, the background is extended automatically
(extend_bg.py, same art, ~$0.07) and the card is fitted again; --no-extend disables it.
Writes _work/run.json with the fit_crop report of every candidate (needs_regen flags).
Previous results for regenerated slots are moved to _work/old/.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

S = Path(__file__).resolve().parent
GENERATORS = {"openai": "openai_generate.py", "lora": "lora_generate.py"}


def generator_script(name):
    """'openai' / 'lora' or a path to any script with the same CLI contract."""
    path = S / GENERATORS[name] if name in GENERATORS else Path(name)
    if not path.exists():
        sys.exit(f"generator not found: {name} (known: {', '.join(GENERATORS)} or a path to a script)")
    return path


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def run(cmd):
    r = subprocess.run([sys.executable] + [str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-800:])
    return r.stdout


def bg_hint(c):
    k = c["category"]
    if k == 1:
        return f"plain {c['background_color']} gradient with {c.get('background_pattern', '')}"
    if k == 2:
        return f"{c['background_color']} wall and {c.get('floor_color', c['background_color'])} floor"
    if k == 3:
        return f"{c['background_color']} {c.get('backdrop', 'wall')} behind and {c.get('surface', '')} below"
    return f"{c.get('scene', '')}, clear blue sky above the object (no cloud directly above it)"


def fit_args(card):
    """Per-card fit options from set.json: "fit": {"margins": "0.18,0.06,0.08", "center": "mass", "paste": "object"}
    (paste: how extend_bg.py puts the original back; "object" avoids a square seam on a plain sky)."""
    f = card.get("fit") or {}
    return (["--margins", f["margins"]] if f.get("margins") else []) + (["--center", f["center"]] if f.get("center") else [])


def process(card, vdir, n, auto_extend=True, quality="medium", generator="openai"):
    nn = f"{card['slot']:02d}"
    work, alt = vdir / "_work", vdir / "_alt"
    name = f"{nn}_{slug(card['label'])}"
    stamp = time.strftime("%H%M%S")
    for old in list(vdir.glob(f"{nn}_*.png")) + list(alt.glob(f"{nn}_*.png")):
        (work / "old").mkdir(exist_ok=True)
        shutil.move(str(old), work / "old" / f"{stamp}_{old.name}")
    t0 = time.time()
    out = json.loads(run([generator_script(generator), "--prompt-file", work / f"{nn}_prompt.txt",
                          "--category", card["category"], "--out", work / f"{nn}_gen.png", "--n", n,
                          "--quality", quality]))
    reports = []
    for i, gen in enumerate(out["saved"]):
        gen = Path(gen)
        cut = gen.with_name(gen.stem + "_cutout.png")
        run([S / "remove_bg.py", "--image", gen, "--out", cut])
        if i == 0:
            final = vdir / f"{name}.png"
        else:
            alt.mkdir(exist_ok=True)
            final = alt / f"{name}_{i + 1}.png"
        rep = json.loads(run([S / "fit_crop.py", "--image", gen, "--cutout", cut, "--out", final,
                              "--category", card["category"], "--game-size", "430x480"] + fit_args(card)))
        if rep.get("needs_regen") and auto_extend:
            # object does not fit the safe zone: extend the background (same art) and fit again
            ext = gen.with_name(gen.stem + "_ext.png")
            extcut = gen.with_name(gen.stem + "_ext_cutout.png")
            paste = (card.get("fit") or {}).get("paste") or ("object" if card["category"] in (1, 2) else "full")
            run([S / "extend_bg.py", "--image", gen, "--out", ext, "--hint", bg_hint(card), "--paste", paste])
            run([S / "remove_bg.py", "--image", ext, "--out", extcut])
            rep = json.loads(run([S / "fit_crop.py", "--image", ext, "--cutout", extcut, "--out", final,
                                  "--category", card["category"], "--game-size", "430x480"] + fit_args(card)))
            rep["extended"] = True
        rep["file"] = str(final.relative_to(vdir))
        reports.append(rep)
    return {"slot": card["slot"], "label": card["label"], "seconds": round(time.time() - t0, 1),
            "usage": out.get("usage"), "candidates": reports}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("variant_dir")
    p.add_argument("--slots", nargs="*", type=int)
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--no-extend", action="store_true",
                   help="do not auto-extend the background when the object misses the safe zone (~$0.07 per extension)")
    p.add_argument("--quality", default="medium", choices=["low", "medium", "high"],
                   help="high: cleaner metal/glass, less noise (for hero cards; ~3x the price)")
    p.add_argument("--generator", default="openai",
                   help="openai (default) | lora (in-house model, see lora_generate.py) | path to a script with the same contract")
    p.add_argument("--keep-prompts", action="store_true", help="do not rebuild prompts (use hand-edited _work/NN_prompt.txt)")
    a = p.parse_args()

    vdir = Path(a.variant_dir)
    generator_script(a.generator)  # fail early on a wrong name
    plan = json.loads((vdir / "set.json").read_text(encoding="utf-8"))
    if not a.keep_prompts:
        print(run([S / "build_prompts.py", vdir / "set.json"]).split('"prompts"')[0].strip().rstrip(","), file=sys.stderr)
    cards = [c for c in plan["cards"] if not a.slots or c["slot"] in a.slots]

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(process, c, vdir, a.n, not a.no_extend, a.quality, a.generator): c for c in cards}
        for f, c in futs.items():
            try:
                results.append(f.result())
            except Exception as e:  # keep going with the other slots
                errors.append({"slot": c["slot"], "error": str(e)})

    log_path = vdir / "_work" / "run.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    for r in results:
        log[str(r["slot"])] = r
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    summary = [{"slot": r["slot"], "label": r["label"],
                "needs_regen": [c["needs_regen"] for c in r["candidates"]],
                "margins": [c.get("margins_pct") for c in r["candidates"]]} for r in sorted(results, key=lambda r: r["slot"])]
    print(json.dumps({"done": summary, "errors": errors}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

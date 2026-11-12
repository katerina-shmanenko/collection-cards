#!/usr/bin/env python3
"""Builds an HTML contact sheet for every set variant in a theme folder.

Usage: python3 contact_sheet.py output/<theme>
Expects output/<theme>/<variant>/NN_*.png and optional set.json per variant.
Writes output/<theme>/index.html (5x2 grid per variant, like the in-game window).
Standard library only.
"""
import html
import re
import json
import sys
from pathlib import Path


def card_meta(set_json, slot):
    for card in set_json.get("cards", []):
        if card.get("slot") == slot:
            return card
    return {}


def build(theme_dir: Path) -> Path:
    blocks = []
    for variant in sorted(p for p in theme_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        plan = {}
        plan_path = variant / "set.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        cells = []
        for img in sorted(variant.glob("[0-9][0-9]_*.png")):
            if re.search(r"_\d+x\d+$", img.stem):
                continue  # skip game-size copies
            slot = int(img.name[:2])
            meta = card_meta(plan, slot)
            stars = "★" * int(meta.get("rarity", 0))
            label = meta.get("label", img.stem[3:])
            cat = meta.get("category", "?")
            cells.append(
                f'<figure><div class="stars">{stars}</div>'
                f'<img src="{html.escape(variant.name)}/{html.escape(img.name)}">'
                f'<figcaption>{html.escape(str(label))}<span>cat {cat}</span></figcaption></figure>'
            )
        title = html.escape(f"{variant.name} — {plan.get('set_name', '')}")
        concept = html.escape(plan.get("concept", ""))
        blocks.append(f'<section><h2>{title}</h2><p>{concept}</p><div class="grid">{"".join(cells)}</div></section>')

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(theme_dir.name)}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#1d1b2e;color:#f4f1ff;margin:24px}}
section{{margin-bottom:40px}} h2{{margin:0 0 4px}} p{{opacity:.7;margin:0 0 12px}}
.grid{{display:grid;grid-template-columns:repeat(5,160px);gap:12px}}
figure{{margin:0;background:#2b2840;border-radius:12px;padding:6px;text-align:center}}
figure img{{width:148px;border-radius:8px;display:block;margin:0 auto}}
.stars{{color:#ffd23f;height:18px;font-size:14px}}
figcaption{{font-size:12px;font-weight:700;text-transform:uppercase;margin-top:4px}}
figcaption span{{display:block;font-weight:400;opacity:.5;text-transform:none}}
</style></head><body><h1>{html.escape(theme_dir.name)}</h1>{"".join(blocks)}</body></html>"""
    out = theme_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 contact_sheet.py output/<theme>")
    print(build(Path(sys.argv[1])))

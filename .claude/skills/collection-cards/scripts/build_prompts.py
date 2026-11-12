#!/usr/bin/env python3
"""Assemble generation prompts from a set plan (set.json) and check set rules.

Prompt = [A style block] + [set style_mood, optional] + [category template] + [key features / camera] + [B bans].
All text comes from the skill's own files, so editing rules/art_style.md or
templates/prompt_templates.md changes every future prompt:
  - A, B blocks and the shape->camera table: rules/art_style.md
  - category templates and the camera block:   templates/prompt_templates.md

Usage:
  python3 build_prompts.py output/<collection>/<theme>/<variant>/set.json
Writes <variant>/_work/NN_prompt.txt and prints set-rule checks as JSON
({"ok": bool, "problems": [...], "warnings": [...], "prompts": [...]}).
problems = hard rules (fix before generating); warnings = soft rules from
set_principles.md / art_style.md F that need a human look (similar neighbour
backgrounds, scale/category balance, story-detail count, long object_color).
Colour PAIRS (art_style F) and repeats across the collection are not checked
automatically — check them by eye against the table and COLLECTION.md.

Optional card fields used by templates (besides the schema's core fields):
  cat 1: background_pattern     cat 2: floor_color, wall_variant
  cat 3: surface, backdrop      cat 4: scene
Standard library only.
"""
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RARITY = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]


def code_block_after(text, heading_prefix):
    i = text.find(heading_prefix)
    if i < 0:
        sys.exit(f"heading not found: {heading_prefix}")
    m = re.search(r"```\n(.*?)\n```", text[i:], re.S)
    return m.group(1).strip()


def load_rules():
    art = (SKILL / "rules/art_style.md").read_text(encoding="utf-8")
    tpl = (SKILL / "templates/prompt_templates.md").read_text(encoding="utf-8")
    cameras = dict(re.findall(r"^\| `(\w+)`[^|]*\| `([^`]+)`", art, re.M))
    return {
        "A": code_block_after(art, "## A."),
        "B": code_block_after(art, "## B."),
        "camera_block": code_block_after(tpl, "## Camera"),
        "cat": {c: code_block_after(tpl, f"## Категория {c}") for c in (1, 2, 3, 4)},
        "cameras": cameras,
    }


class Fields(dict):
    def __missing__(self, key):
        return ""


def build_prompt(card, R, mood=""):
    f = Fields({k: v for k, v in card.items() if isinstance(v, (str, int))})
    f.setdefault("background_pattern", "soft radial sunburst rays")
    f.setdefault("floor_color", f["background_color"])
    f.setdefault("surface", "wooden planks")
    f.setdefault("backdrop", "wall")
    f["camera"] = card.get("camera") or R["cameras"].get(card.get("shape", ""), "")
    if card.get("story_detail"):
        f["story_detail"] = (f", with {card['story_detail']} in {card.get('detail_color', 'a contrasting color')}"
                             f" that clearly contrasts with the {card.get('object_color', '')} object")
    subject = R["cat"][card["category"]].format_map(f)
    if card["category"] == 4 and any(w in (card.get("scene", "") + card.get("background_color", "")).lower()
                                     for w in ("night", "twilight", "space", "nebula")):
        # night / space is allowed only when it is the essence of the object (art_style.md C)
        subject = (subject.replace("in a simplified bright daytime environment", "in a simplified bright environment")
                   .replace("Saturated blue sky with fluffy white clouds where the sky is visible.",
                            "Bright saturated night scene with glowing lights, not dark, not gloomy, no clouds."))
    if card.get("sky"):  # e.g. a pink Martian sky, or a clear sky without clouds that could be mistaken for smoke
        subject = subject.replace("Saturated blue sky with fluffy white clouds where the sky is visible.",
                                  card["sky"].rstrip(". ") + ".")
    if card.get("framing"):  # e.g. a smaller vehicle with space around it instead of the default close-up
        subject = re.sub(r"filling about \d+% of the frame[^.]*\.", card["framing"].rstrip(". ") + ".", subject)
    camera = R["camera_block"].format_map(f).replace(". .", ".").replace("..", ".")
    if not card.get("key_features"):
        camera = "\n".join(l for l in camera.splitlines() if not l.startswith("Key recognizable"))
    parts = [R["A"]] + ([mood] if mood else []) + [subject, camera.replace("\n", " "), R["B"]]
    return " ".join(parts)


SOFT = ("soft", "muted", "warm", "deep", "saturated", "bright", "light", "dusty", "rich", "pale", "fresh", "dark")


def tone(name):
    """normalise a background colour name for 'too similar' checks: 'soft sky blue' ~ 'sky blue'."""
    return " ".join(w for w in name.lower().replace("-", " ").split() if w not in SOFT)


def warnings_for(plan):
    cards = sorted(plan["cards"], key=lambda c: c["slot"])
    w = []
    from collections import Counter
    sc = Counter(c.get("scale") for c in cards)
    for k in ("small", "medium", "large"):
        if sc.get(k, 0) < 2:
            w.append(f"scale '{k}': {sc.get(k, 0)} card(s), rule is at least 2 of each")
    cc = Counter(c["category"] for c in cards)
    for k in (1, 2, 3, 4):
        if not 2 <= cc.get(k, 0) <= 3:
            w.append(f"category {k}: {cc.get(k, 0)} card(s), guideline is 2-3")
    sd = sum(1 for c in cards if c.get("story_detail"))
    if not 4 <= sd <= 6:
        w.append(f"story_detail on {sd} cards, guideline is 4-6")
    bg = {c["slot"]: tone(c["background_color"]) for c in cards}
    for s_ in range(1, 11):
        for n in ([s_ + 1] if s_ % 5 else []) + ([s_ + 5] if s_ <= 5 else []):
            if s_ in bg and n in bg and bg[s_] == bg[n]:
                w.append(f"slots {s_} and {n} are neighbours with very similar backgrounds ('{bg[s_]}')")
    for c in cards:
        if len(c.get("object_color", "").split()) > 4:
            w.append(f"slot {c['slot']}: object_color is long ('{c['object_color']}') — keep 1-4 words, details go to key_features")
    return w


def check(plan):
    cards = sorted(plan["cards"], key=lambda c: c["slot"])
    problems = []
    if [c["slot"] for c in cards] != list(range(1, 11)):
        problems.append("slots must be 1..10")
    if [c["rarity"] for c in cards] != RARITY:
        problems.append("rarity must be 1,1,2,2,3,3,4,4,5,5 by slot")
    cats = [c["category"] for c in cards]
    for k in (1, 2, 3, 4):
        if cats.count(k) == 0:
            problems.append(f"category {k} missing")
    if len({c.get("object_type") for c in cards}) < 4:
        problems.append("fewer than 4 object types")
    if len({c.get("scale") for c in cards}) < 3:
        problems.append("fewer than 3 scales")
    bg = {c["slot"]: c["background_color"].lower() for c in cards}
    if len(set(bg.values())) < 6:
        problems.append("fewer than 6 different background colors")
    for s in range(1, 11):
        for n in ([s + 1] if s % 5 else []) + ([s + 5] if s <= 5 else []):
            if s in bg and n in bg and bg[s] == bg[n]:
                problems.append(f"slots {s} and {n} are grid neighbours with the same background '{bg[s]}'")
    for c in cards:
        if not c.get("key_features"):
            problems.append(f"slot {c['slot']}: key_features empty")
    return problems


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 1)
    plan_path = Path(sys.argv[1])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    R = load_rules()
    work = plan_path.parent / "_work"
    work.mkdir(exist_ok=True)
    written = []
    for c in plan["cards"]:
        p = work / f"{c['slot']:02d}_prompt.txt"
        p.write_text(build_prompt(c, R, plan.get("style_mood", "")) + "\n", encoding="utf-8")
        written.append(str(p))
    problems = check(plan)
    print(json.dumps({"ok": not problems, "problems": problems, "warnings": warnings_for(plan), "prompts": written},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

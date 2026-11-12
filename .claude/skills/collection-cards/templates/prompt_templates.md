# Шаблоны промптов по категориям

Итоговый промпт = **[A стиль] + [шаблон категории] + [Camera] + [B запреты]** (A и B — из `rules/art_style.md`).
Плейсхолдеры `{...}` берутся из `set.json`. `{story_detail}`, если поле непустое, подставляется как `, with {story_detail} in {detail_color} that clearly contrasts with the {object_color} object`.

## Camera и признаки (добавляются к любой категории)
```
Key recognizable features that must be clearly visible: {key_features}.
Camera and pose: {camera}. {pose}. The whole object stays centered with equal margins left and right.
```

## Категория 1 — объект в воздухе
```
Subject: a {object_color} {object}{story_detail}, floating in the air, large and prominent but fully visible: it spans about 60% of the image width, with clear even margins of background on the left and right. Background: plain {background_color} gradient with {background_pattern}, soft and slightly muted, not neon, evenly lit all the way to the corners (no darkening or vignette at the edges).
```
Про размер: «60% of the image width» относится к холсту генерации 1248×1248; после `fit_crop.py` (окно 9:10 с полями категории) объект занимает ~75–85% ширины финальной карточки, как требует `art_style.md` D.
`background_pattern` ∈ radial sunburst rays / concentric circles / soft swirl / vertical stripes / soft diagonal waves / faint repeating pattern of small {motif} icons.

## Категория 2 — объект на простой поверхности
```
Subject: a {object_color} {object}{story_detail}, standing on a simple flat {floor_color} surface, fully visible: the whole object fits inside the central 65% of the image width, with empty background on the left and right. Behind it a plain vertical wall in {background_color}{wall_variant}.
```
`wall_variant`: "" / " with soft vertical stripes" / " with a soft spotlight glow".

## Категория 3 — объект на реалистичной поверхности
```
Subject: a {object_color} {object}{story_detail}, placed on a realistic {surface} seen close-up, filling about 75% of the frame. Behind it a simple backdrop: {background_color} {backdrop}. The backdrop must be {background_color}.
```
`surface`: wooden planks / tiled floor / sand / stage floor / stone pavement…; `backdrop`: wall / curtain / light rays.

## Категория 4 — объект в окружении
```
Subject: a {object_color} {object}{story_detail} in a simplified bright daytime environment: {scene}. Saturated blue sky with fluffy white clouds where the sky is visible. Keep the environment very simple, like a game icon: only the object, the sky and a plain ground or horizon line; at most ONE small simple supporting element far in the background; no extra buildings, props, fences, paths, signs, lamps or small decorative details. The {object} remains the clear central focus, filling about 80% of the frame; it may be slightly cropped by the frame edges. The dominant background color of the scene is {background_color}.
```
Для ночных объектов (только если ночь — суть объекта) замени вторую фразу на: `Bright saturated night scene with glowing lights, not dark.`

# Исследование инструментов (08.11.2026)

## Magnific MCP — главный кандидат на генерацию
Источник: https://docs.magnific.com/modelcontextprotocol

- **Подключение к Claude Code:** `claude mcp add --transport http magnific https://mcp.magnific.com`, вход через OAuth (браузер). API-ключ не нужен.
- **Оплата:** тратит те же кредиты, что и приложение. Подписочное «безлимитное» использование действует только в веб-интерфейсе, а вызовы через MCP/API списывают кредиты. → **Проверить завтра:** `account_balance` и `simulate_cost` (бесплатно) до первой генерации.
- **Документация описывает 236 инструментов.** Нужные нам:

| Задача | Инструмент |
|---|---|
| Генерация по тексту + референсам (стиль/объект/композиция) | `images_generate` |
| Каталог моделей и их настройки | `images_models_list`, `images_models_settings` |
| Перерисовка в стиле картинки-референса | `images_restyle` |
| Вариации | `images_variations`, `images_reimagine` |
| Удаление/замена фона | `images_remove_background`, `images_replace_background` |
| Апскейл (наши референсы всего 117×131 px) | `images_upscale` |
| Загрузка своих картинок | `creations_request_upload` → `creations_finalize_upload` |
| Ожидание и скачивание результата | `creations_wait`, `creations_get` (возвращает URL) |
| Сохранённый стиль/библиотека (1–6 картинок) | `library_create` |
| **Запуск сетапов из интерфейса** | `spaces_list`, `spaces_run`, `spaces_run_status`, `flows_list`, `flows_run`, `flows_wait` |
| Оценка стоимости | `simulate_cost`, `account_balance` |

- **Модели внутри (по сайту Magnific, проверить в `images_models_list`):** Nano Banana 2 / Pro, Seedream 4.5 / 5, Flux.2 Pro / Max, Flux Kontext, Imagen 4, GPT-image, Recraft V4. Многие принимают референсы: Seedream 5 Lite до 14, Flux.2 Pro до 10.
- **Не задокументировано:** параметры `images_generate` (соотношение сторон, число картинок, формат референсов). Смотреть в живом списке инструментов после подключения.

### Вывод
Самое важное: **сетапы из интерфейса Magnific (Spaces/Flows), вероятно, можно запускать из Claude Code** через `spaces_run` / `flows_run`. Это закрывает разрыв «сетап ручной, а нужна автономность». Завтра проверяем:
1. Видны ли ваши Spaces в `spaces_list`.
2. Можно ли подать на вход свой промпт/объект при запуске.

## Факты после подключения (09.11)
- Подключено через коннектор приложения Claude (не через CLI-запись `magnific`).
- План Premium, `isUnlimitedMode: false`: каждая генерация через MCP списывает кредиты.
- Spaces: 16 штук, под карточки сетапа пока нет. Flows: 0.
- `images_generate`: до 12 референсов, типы `style` / `image` / `character` / `product`, `count` до 8 вариаций за один вызов, есть `seed` для воспроизводимости. Прозрачный фон умеют только GPT 2 / 2.5 / 2.6.
- Рекомендация Magnific по умолчанию — Nano Banana 2.1 (`sota`, rank 1). Для стилизации — Magnific One (rank 2).

### Цена одной картинки (simulate_cost, без референсов)
| Модель | Настройки | Кредиты |
|---|---|---|
| Seedream 5 Flash | 1:1, 1.5k | 35 |
| GPT 2.6 | 1:1, 1k, medium | 40 |
| Nano Banana 2.1 | 4:5, 1k | 50 |
| Flux.2 Pro | 4:5, 1k | 50 |
| Nano Banana 2 Lite | 4:5 | 60 |
| Qwen Image 3.0 | 4:5 | 60 |
| Recraft V4 | 4:5 | 60 |
| Nano Banana 2 | 4:5, 1k | 75 |
| Magnific One | 1:1, 1k | 100 |
| Апскейл | от размера | 90–1080 |

### Бюджет
- Финал: 3 сета × 3 варианта × 10 карт = 90 картинок + ~50% на перегенерацию ≈ 135 × ~45 ≈ **6 000 кредитов**.
- Бенчмарк: 4 объекта × 5 моделей ≈ **1 000**.
- Итого нужно **~7 000–8 000** кредитов.

## n8n — опциональная вторая обёртка
- **Облако:** около €20–24/мес (Starter, ~2 500 запусков). Есть 14-дневный бесплатный триал без карты. → **Для тестового хватит триала, покупать не нужно.**
- **Подключение Magnific:** узел MCP Client Tool подключается к внешнему MCP-серверу по HTTP. Совместимость с OAuth Magnific нужно проверить.
- **LLM в n8n:** подписка Claude за $20 сюда не подходит, нужен API-ключ. Бесплатный вариант — Gemini API (Google AI Studio).
- **Форма для гейм-дизайнера:** узел Form Trigger, веб-форма по ссылке.
- **Решение:** делаем, только если на день 3 останется время. Иначе даём на Miro схему «следующего шага».

## ComfyUI — следующий шаг
Подключается к нашему скиллу как сменный генератор: переходник `lora_generate.py` готов (README, раздел «Свой генератор»). Имеет смысл, когда у студии есть сервер ComfyUI и LoRA под игру.

## Источники
- https://docs.magnific.com/modelcontextprotocol
- https://www.magnific.com/api/pricing
- https://www.magnific.com/ai/docs/image-ai-models
- https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp/
- https://n8n.io/pricing

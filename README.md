# YouTube Digest

[English](#english) | [Русский](#русский)

---

## Русский

Telegram-бот, который извлекает применимые идеи из YouTube-видео без необходимости их смотреть.

### Как работает

1. Кидаешь боту ссылку на YouTube
2. Бот вытягивает субтитры (авто или ручные)
3. LLM анализирует транскрипт и извлекает конкретные идеи, применимые к твоему контексту
4. Получаешь список идей с тегами и кнопками выбора
5. Отбираешь нужные → сохраняются в markdown-бэклог

### Особенности

- **Без саммари** — сразу идеи из полного транскрипта, ничего не теряется
- **Персональный контекст** — LLM знает про твои бизнесы, интересы, жизненную ситуацию и фильтрует идеи под тебя
- **Выборочное сохранение** — inline-кнопки ✅/⬜ на каждую идею, сохраняешь только нужные
- **Единый бэклог** — все идеи в одном `ideas-backlog.md` с чекбоксами, тегами и ссылками на источник
- **Любая тематика** — бизнес, здоровье, воспитание, отношения, психология, продуктивность
- **Переключение моделей** — `/model` в боте: Haiku 4.5 (~$0.05/видео), Sonnet 4.6 (~$0.25/видео), Gemini Flash (~$0.01/видео). Выбор сохраняется для всех последующих видео
- **Понятные ошибки** — пустой баланс, лимит запросов, невалидный ключ — бот скажет что именно не так

### Команды бота

| Команда | Описание |
|---|---|
| `/start` | Справка и текущая модель |
| `/model` | Переключить модель анализа |
| Ссылка | Извлечь идеи из видео |

### Установка

```bash
git clone https://github.com/sollidol/youtube-digest.git
cd youtube-digest
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
# Заполни .env — токены и свой контекст
```

### Настройка .env

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_OWNER_ID` | Твой Telegram user ID (whitelist) |
| `OPENROUTER_API_KEY` | Ключ OpenRouter |
| `OPENROUTER_MODEL` | Модель по умолчанию (`anthropic/claude-haiku-4-5`) |
| `OWNER_CONTEXT` | Описание тебя: бизнесы, интересы, ситуация — чем подробнее, тем точнее идеи |
| `IDEA_TAGS` | Теги для категоризации идей через запятую |

### Запуск

```bash
.venv/bin/python -m youtube_digest
```

Или через systemd (см. `systemd/youtube-digest.service`).

---

## English

Telegram bot that extracts actionable ideas from YouTube videos so you don't have to watch them.

### How it works

1. Send a YouTube link to the bot
2. Bot pulls subtitles (auto-generated or manual)
3. LLM analyzes the full transcript and extracts concrete ideas relevant to your context
4. You get a list of ideas with tags and selection buttons
5. Pick the ones you want → saved to a markdown backlog

### Features

- **No summary layer** — ideas extracted directly from the full transcript, nothing gets lost
- **Personal context** — LLM knows about your businesses, interests, and life situation, filters ideas for you
- **Selective saving** — inline ✅/⬜ buttons per idea, save only what matters
- **Single backlog** — all ideas in one `ideas-backlog.md` with checkboxes, tags, and source links
- **Any topic** — business, health, parenting, relationships, psychology, productivity
- **Model switching** — `/model` in bot: Haiku 4.5 (~$0.05/video), Sonnet 4.6 (~$0.25/video), Gemini Flash (~$0.01/video). Choice persists for all subsequent videos
- **Clear error messages** — empty balance, rate limits, invalid key — bot tells you exactly what's wrong

### Bot commands

| Command | Description |
|---|---|
| `/start` | Help and current model |
| `/model` | Switch analysis model |
| Link | Extract ideas from video |

### Setup

```bash
git clone https://github.com/sollidol/youtube-digest.git
cd youtube-digest
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
# Fill in .env — tokens and your personal context
```

### .env configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | Your Telegram user ID (whitelist) |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_MODEL` | Default model (`anthropic/claude-haiku-4-5`) |
| `OWNER_CONTEXT` | Describe yourself: businesses, interests, situation — more detail = better ideas |
| `IDEA_TAGS` | Comma-separated tags for categorizing ideas |

### Run

```bash
.venv/bin/python -m youtube_digest
```

Or via systemd (see `systemd/youtube-digest.service`).

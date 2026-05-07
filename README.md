# Fintech High-Risk News Bot

Личная автоматизация — собирает новости по high-risk fintech (crypto/VASP, EMI/PSP/PI/MSB, gambling/iGaming, adult-PSP, sanctions, AML) из RSS регуляторов и прессы, классифицирует через Claude, кросс-проверяет между источниками и публикует в Telegram-канал.

Расписание: 2 раза в день (дайджест) + раз в час (breaking) + воскресенье (сводка недели).

> Не клиентский деливерабл. Это внутренний инструмент в папке `Consulting/`.

---

## Архитектура

```
RSS (регуляторы + пресса)
   ↓
fetcher.py        — feedparser, фильтр по дате
   ↓
classifier.py     — Claude API: relevance, category, importance, RU summary
   ↓
verifier.py       — Claude кластеризует по событиям, считает независимые источники
                    ✅ если ≥2 независимых домена (или regulator + press)
                    ⚠️ иначе
   ↓
poster.py         — Telegram Bot API
   ↓
state.py          — data/state.json: что уже постили, weekly buffer
```

## Локальная проверка (опционально)

```bash
cd fintech-news-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# заполни .env (создан в репо локально, в git не попадёт)
python -m src.main digest      # тест-прогон
```

## Развёртывание в GitHub Actions

### 1. Создай GitHub-репозиторий

Через web или `gh` CLI. Сделай **приватным**.

```bash
cd /Users/pogreb/Desktop/Work/Consulting/fintech-news-bot
git init
git add .
git commit -m "init"
gh repo create fintech-news-bot --private --source=. --push
# или вручную: создай репо на github.com → git remote add origin <url> → git push -u origin main
```

### 2. Добавь Secrets

`Settings → Secrets and variables → Actions → New repository secret`:

| Name                   | Value                          |
|------------------------|--------------------------------|
| `TELEGRAM_BOT_TOKEN`   | токен от @BotFather            |
| `TELEGRAM_CHANNEL_ID`  | `@your_channel` или `-100…`    |
| `ANTHROPIC_API_KEY`    | `sk-ant-…`                     |

### 3. Включи workflow permissions

`Settings → Actions → General → Workflow permissions → "Read and write permissions"`. Это нужно, чтобы бот коммитил обратно `data/state.json`.

### 4. Запусти руками для проверки

`Actions → digest → Run workflow`. Через ~30 сек должны полететь посты в канал.

После этого расписание (cron) подхватит само.

## Источники

См. `src/sources.py`. Подкручивать: добавлять/убирать RSS, менять `weight`. Регуляторы без RSS (OFAC, VARA, DFSA) — TODO, нужны HTML-скраперы.

## Расходы

- Telegram: бесплатно
- GitHub Actions: бесплатные лимиты с запасом для приватных репо (~2000 мин/мес; этот бот ест ~3-5 мин/прогон)
- Claude API: ориентир $5-15/мес при описанной частоте

## Когда что-то ломается

- `Actions` → последний прогон → смотри логи: где упало
- Чаще всего: RSS-источник переехал — обнови URL в `sources.py`
- `data/state.json` распух — пруны срабатывают сами (60 дней), но можно почистить руками

## Ротация секретов

Если token/key утекли:
- Telegram: `@BotFather → /revoke`
- Anthropic: console → API Keys → удалить старый, создать новый
- Обнови GitHub Secrets и локальный `.env`

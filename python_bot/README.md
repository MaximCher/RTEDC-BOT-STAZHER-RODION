# SRVT Bot (Python / aiogram)

Этот контур — целевая миграция SRVT‑бота на **Python 3.11 + aiogram + PostgreSQL + pgvector + OpenAI** по MAXCAPITAL‑архитектуре.

## Быстрый старт (Docker)

Из корня репозитория:

```bash
cd python_bot
cp env.template .env
mkdir -p data
```

Положите PDF с базой знаний субсидий в:
- `python_bot/data/subsidies.pdf`

Запуск сервисов:

```bash
docker compose up -d --build
```

Проверка статуса:

```bash
docker compose ps
docker compose logs --tail=50 bot
docker compose logs --tail=50 web
```

## Инжест PDF в RAG (pgvector)

После запуска `db` и `bot`:

```bash
docker compose exec bot python scripts/ingest_pdf_subsidies.py --pdf data/subsidies.pdf --name "subsidies.pdf"
```

Скрипт:
- извлекает текст из PDF,
- режет на чанки,
- считает embeddings `text-embedding-3-small`,
- сохраняет в таблицу `documents`.

## Тестирование в Telegram

1) Откройте бота → `/start`.
2) Выберите услугу **«💰 Субсидии и льготное финансирование»**.
3) Пройдите анкету или сразу нажмите **«🔎 Вопрос по субсидиям»** (RAG‑чат).
4) Для RAG‑ответов убедитесь, что вы уже выполнили **инжест PDF**.
5) Нажмите **«📩 Передать эксперту»** → отправьте ФИО + телефон → (если настроен Bitrix webhook) создастся лид.

## Админ‑панель (FastAPI)

Админка поднимается сервисом `web` и доступна на:
- `http://localhost:8000`

Пароль берётся из `.env`:
- `ADMIN_PASSWORD=...`

Функции:
- список пользователей (агрегация `dialog_messages`)
- история диалога по `user_id`
- статистика (уникальные пользователи / сообщения / лиды из `bitrix_leads`) + фильтр по датам
- CSV экспорт диалогов: `GET /api/export.csv` (после логина)
- health endpoint: `GET /health`

## Переменные окружения (минимум)

- `TELEGRAM_BOT_TOKEN`
- `MANAGER_CHAT_IDS` (необязательно)
- `POSTGRES_*`
- `OPENAI_API_KEY` (нужен для RAG и AI‑ответов)
- `BITRIX24_WEBHOOK_URL` (опционально, можно пустым на этапе разработки)
- `ADMIN_PASSWORD` (для админки)

## Prod (Nginx reverse proxy)

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl http://localhost/health
```

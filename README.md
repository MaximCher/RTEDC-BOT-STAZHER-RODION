# SRVT Assistant Telegram Bot

SRVT Assistant — консультационно-продажный Telegram-бот на Telegraf + TypeScript для Совета по развитию внешней торговли (СРВТ). Бот выступает младшим консультантом: быстро уточняет задачу предпринимателя, формирует ценность и переводит пользователя в лид-форму.

## Возможности
- Главное меню из трёх CTA: «🧭 Подобрать решение», «📋 Услуги СРВТ», «👨‍💼 Связаться с экспертом».
- Объединённый сценарий «🧭 Подобрать решение» — бот ведёт диалог с предпринимателем, задаёт уточняющие вопросы, опирается на mini-RAG (`src/services/knowledgeBase.ts`) и OpenAI, формирует summary/рекомендации/оценку риска, логирует кейс в БД и ведёт к лид-форме в один клик.
- Раздел «📋 Услуги СРВТ» с направлениями (финансы, логистика, платежи, проверка контрагентов, выход на рынки); внутри блока «💰 Финансирование и субсидии» доступен калькулятор субсидий.
- Калькулятор субсидий опирается на `src/data/subsidies.json`, выводу доступные программы, сумму субсидии и CTA «Передать расчёт эксперту».
- Единая мягкая лид-форма (имя, любой контакт, компания) с автоподхватом имени из Telegram, записью в Prisma/Postgres и уведомлением в `ADMIN_CHAT_ID`.

## Быстрый старт
```bash
cp .env.example .env
# заполните BOT_TOKEN, ADMIN_CHAT_ID, DATABASE_URL, OPENAI_API_KEY
npm install
npx prisma migrate dev --name init
npx prisma generate
npm run dev
```

`npm run dev` запускает `ts-node-dev` с hot-reload. Для продакшена: `npm run build && npm start`.

## PostgreSQL + Prisma
1. Установка Postgres (Ubuntu):
   ```bash
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   ```
2. Создание БД и пользователя:
   ```bash
   sudo -u postgres psql -c "CREATE DATABASE srvt_bot;"
   sudo -u postgres psql -c "CREATE USER srvt_user WITH ENCRYPTED PASSWORD 'srvt_pass';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE srvt_bot TO srvt_user;"
   ```
3. Пример строки подключения (укажите свои параметры) в `.env`:
   ```
   DATABASE_URL="postgresql://srvt_user:srvt_pass@localhost:5432/srvt_bot?schema=public"
   ```
4. Применить миграции и сгенерировать клиент:
   ```bash
   npx prisma migrate dev --name init
   npx prisma generate
   ```

## OpenAI
1. Получите API-ключ в [OpenAI Platform](https://platform.openai.com/).
2. Пропишите `OPENAI_API_KEY` в `.env`.
3. Сценарий «🧭 Подобрать решение» использует модель `gpt-4o-mini` и знания из `src/knowledge/*.md`. При отсутствии ключа бот перейдёт на fallback-логику и сообщит пользователю о необходимости эксперта.

## Структура
```
prisma/            # Prisma schema
src/
  bot/             # Telegraf конфигурация, хендлеры, клавиатуры, middleware
  data/            # subsidy rules
  knowledge/       # markdown-статьи базы знаний СРВТ
  services/        # lead processor, AI assistant, subsidy calculator, Prisma client
  types/           # Lead, Subsidy, Session и т.д.
  utils/           # Логер и вспомогательные утилиты
index.ts           # Точка входа
```

## База знаний СРВТ и mini-RAG
- Файлы находятся в `src/knowledge/*.md` (финансирование, логистика, платежи, проверка партнёров, субсидии, экспорт, FAQ).
- Сервис `src/services/knowledgeBase.ts` разбивает статьи на чанки (≈900 символов), кэширует их и подбирает 1–4 релевантных блока по направлению/ключевым словам.
- `src/services/aiAssistant.ts` получает `kbContext` и список статей, отдаёт OpenAI и просит вернуть JSON с направлением, summary, рекомендациями, оценкой риска/потенциала и признаками использования базы знаний.
- В `CaseLog.raw` и `Lead.metadata` сохраняются статьи/флаги `kbUsed`, чтобы менеджер видел контекст источников.

## Импорт программ субсидий
1. Экспортируйте таблицу из Google Docs/Sheets в файл `src/data/subsidies_source.xlsx` (или `.csv`). Рекомендуемые колонки (английские или русские заголовки): `code`, `title`, `description`, `cost_types`, `sectors`, `regions`, `keywords`, `requires_export`, **`min_budget` (`Минимальная сумма поддержки`)**, **`max_budget` (`Максимальная сумма поддержки`)**, `coverage_rate`, `max_amount`, `conditions`, `recipient`, `docs_required`, `notes`. Можно использовать синонимы — импорт конвертирует ключи к snake_case и ищет поля по списку алиасов.
2. Файл обязательно сохраняйте в UTF-8 **без BOM** и без дополнительных перекодировок — иначе русские названия превратятся в кракозябры.
3. Значения в списках перечисляйте через запятую/точку с запятой (например, `ip; ooo; self` для форм, `logistics,certification` для типов затрат).
4. Все суммы указывайте в рублях (целые числа). Разрешён формат `3000000`, `3 000 000`, `3 000 000 ₽` — импорт очищает все символы, кроме цифр. Проценты (`coverage_rate`) записывайте как `0.7`, `70`, `35%` и т.п.
5. Перед повторным импортом при полной замене данных:
   ```bash
   npx prisma migrate dev        # если меняли схему
   npx prisma studio             # при необходимости, чтобы открыть таблицу
   psql "$DATABASE_URL" -c 'TRUNCATE TABLE "SubsidyProgram" RESTART IDENTITY;'
   npm run import:subsidies
   ```
6. Для стандартного импорта достаточно выполнить:
   ```bash
   npm run import:subsidies
   ```
   Скрипт выведет список распознанных колонок и количество загруженных программ. Повторный импорт выполняет upsert по полю `code`.

## Расширенный scoring лидов
- Базовый балл зависит от сценария (подбор решения, субсидии, услуги, контакт менеджера, legacy-квиз).
- Дополнительные баллы начисляются за факторы из `metadata`: крупные бюджеты, наличие экспорта, приоритетные рынки (Китай, ОАЭ, ЕС), риск-ключевые слова («блокировка», «санкции», «не платят»).
- Сервис `src/services/leadScoring.ts` считает `baseScore`, `extendedScore` (1–5) и список `factors`, результат сохраняется в `Lead.score` и `metadata.scoring`.
- Формат уведомления менеджеру (`formatLeadForManager`) теперь показывает числовую оценку и приоритет (🔥/⚡/🌱), чтобы быстрее подхватывать горячие запросы.

## Переменные окружения
- `BOT_TOKEN` — токен Telegram-бота.
- `ADMIN_CHAT_ID` — чат/аккаунт для уведомлений о лид-формах.
- `DATABASE_URL` — строка подключения к Postgres.
- `OPENAI_API_KEY` — ключ OpenAI (опционален, но нужен для AI анализа кейсов).
- `BITRIX_WEBHOOK_URL` — REST-вебхук Bitrix24 с правами `crm.lead.add`.
- `BITRIX_RESPONSIBLE_DEFAULT_ID` — ID ответственного менеджера, на которого заводятся все лиды в Bitrix24.

## Расширение
- Сценарий подбора решений реализован в `src/bot/handlers/caseHandler.ts` (состояние `flow = 'solution'`).
- Субсидийные программы лежат в `src/data/subsidies.json`.
- Обработчик лидов (`services/leadProcessor.ts`) можно интегрировать с CRM или вебхуками.
- Для кастомных сценариев используйте единый `LeadPayload` и call-to-action к `srvt:lead:start:<slug>`; все сценарии должны собирать метаданные и передавать их в лид.
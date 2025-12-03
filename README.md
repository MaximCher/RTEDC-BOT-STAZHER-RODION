# SRVT Assistant Telegram Bot

SRVT Assistant — консультационно-продажный Telegram-бот на Telegraf + TypeScript для Совета по развитию внешней торговли (СРВТ). Бот выступает младшим консультантом: быстро уточняет задачу предпринимателя, формирует ценность и переводит пользователя в лид-форму.

## Возможности
- Плиточное главное меню из 5 CTA: помощь, кейс, субсидии, услуги, связь с менеджером.
- Короткий квалифицирующий квиз «Получить помощь» с генерацией резюме проблемы и переходом в лид-форму.
- Сценарий «Проверить мой кейс» с анализом через OpenAI и логированием кейсов в БД.
- Калькулятор субсидий по правилам (`src/data/subsidies.json`) и CTA на оформление.
- Раздел «Услуги СРВТ» с ценностью по направлениям и кнопкой «Оставить заявку».
- Единая мягкая лид-форма (имя, контакт, компания) с автоподхватом имени, записью в Prisma/Postgres и уведомлением в `ADMIN_CHAT_ID`.

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
3. Сценарий «Проверить мой кейс» будет использовать модель `gpt-4o-mini`. При отсутствии ключа бот автоматически перейдёт на fallback-логику.

## Структура
```
prisma/            # Prisma schema
src/
  bot/             # Telegraf конфигурация, хендлеры, клавиатуры, state-machine
  data/            # subsidy rules
  knowledge/       # markdown-статьи базы знаний СРВТ
  services/        # lead processor, AI assistant, subsidy calculator, Prisma client
  types/           # Lead, Subsidy, Session и т.д.
  utils/           # Логер и вспомогательные утилиты
index.ts           # Точка входа
```

## База знаний СРВТ
- Файлы находятся в `src/knowledge/*.md` (финансирование, логистика, платежи, проверка партнёров, субсидии, экспорт, FAQ).
- Контент — короткие структурированные заметки. Первый заголовок `# ...` используется как название источника.
- Сервис `src/services/knowledgeBase.ts` читает статьи, кэширует их и подбирает релевантные блоки для AI (микро-RAG).
- Чтобы обновить знания, достаточно отредактировать/добавить Markdown-файл и перезапустить бота.

## Расширенный scoring лидов
- Базовый балл зависит от сценария (квиз, кейс, субсидии, услуги, контакт менеджера).
- Дополнительные баллы начисляются за факторы из `metadata`: крупные бюджеты, наличие экспорта, приоритетные рынки (Китай, ОАЭ, ЕС), риск-ключевые слова («блокировка», «санкции», «не платят»).
- Сервис `src/services/leadScoring.ts` считает `baseScore`, `extendedScore` (1–5) и список `factors`, результат сохраняется в `Lead.score` и `metadata.scoring`.
- Формат уведомления менеджеру (`formatLeadForManager`) теперь показывает числовую оценку и приоритет (🔥/⚡/🌱), чтобы быстрее подхватывать горячие запросы.

## Переменные окружения
- `BOT_TOKEN` — токен Telegram-бота.
- `ADMIN_CHAT_ID` — чат/аккаунт для уведомлений о лид-формах.
- `DATABASE_URL` — строка подключения к Postgres.
- `OPENAI_API_KEY` — ключ OpenAI (опционален, но нужен для AI анализа кейсов).

## Расширение
- Квизы расширяются через `bot/states/quizMachine.ts`.
- Субсидийные программы лежат в `src/data/subsidies.json`.
- Обработчик лидов (`services/leadProcessor.ts`) можно интегрировать с CRM или вебхуками.
- Для кастомных сценариев используйте единый `LeadPayload` и call-to-action к `srvt:lead:start:<slug>`.
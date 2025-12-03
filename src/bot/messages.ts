import { Direction, LeadPayload } from '../types/lead';

const directionLabels: Record<Direction, string> = {
  finance: 'Финансирование',
  logistics: 'Логистика',
  payments: 'Платежи',
  analytics: 'Аналитика и проверка партнера',
  other: 'Другое направление'
};

export const messages = {
  welcome: (name?: string): string =>
    `Здравствуйте${name ? `, ${name}` : ''}! Я SRVT Assistant — работаю на базе знаний Совета по развитию внешней торговли и подключаю экспертов под ваш запрос. Выберите, что актуально прямо сейчас 👇`,
  mainMenuHint:
    'Главное меню: помощь, кейсы, субсидии, услуги и прямой контакт. Все сценарии опираются на практику СРВТ.',
  quizIntro:
    'С чем помочь? Выберите направление — опираюсь на базу кейсов СРВТ, задам пару уточняющих вопросов и подберу решение.',
  quizQuestion: (text: string): string => text,
  quizSummary: (directionLabel: string, summary: string): string =>
    `Похоже, у вас запрос по направлению *${directionLabel}*.\n\n${summary}\n\nГотов подключить профильного эксперта — оставьте удобный контакт.`,
  quizClosing: (direction: Direction, summary: string): string => {
    const map: Record<Direction, string> = {
      finance:
        `Итого по вашему финансовому запросу: ${summary}\n\nЭксперт СРВТ может подобрать оптимальные инструменты финансирования, подсказать по субсидиям и вместе с вами подготовить документы. Оставьте контакт, чтобы мы вернулись с готовым вариантом решения.`,
      logistics:
        `По логистике видим ключевые точки: ${summary}\n\nМожем просчитать безопасные маршруты, подобрать перевозчиков и снять риски по таможне. Оставьте контакт — подготовим план и вернёмся с предложением.`,
      payments:
        `В финансовых расчётах выделили: ${summary}\n\nПоможем настроить платежи, разобраться с банками и закрыть валютный контроль. Оставьте контакт, и мы подготовим варианты с конкретными шагами.`,
      analytics:
        `По аналитике и партнёрам видим: ${summary}\n\nМожем провести проверку контрагентов, оценить рынки и выдать рекомендации по выходу. Оставьте контакт — подключим эксперта и подготовим план.`,
      other:
        `Ваш запрос требует индивидуального сопровождения: ${summary}\n\nСоберём команду под конкретную задачу, поможем с партнёрами и запуском. Оставьте контакт, чтобы мы вернулись с персональным предложением.`
    };
    return map[direction];
  },
  quizCta: 'Оставить контакт',
  servicesIntro: 'Экспертиза СРВТ по ключевым направлениям экспорта:',
  serviceDescription: (direction: Direction): string => {
    const descriptions: Record<Direction, string> = {
      finance:
        'Подбираем субсидии, финансирование и меры поддержки. Сопровождаем заявки и защищаем проекты.',
      logistics:
        'Разрабатываем маршруты, страхование и складскую инфраструктуру. Снижаем стоимость и риски поставок.',
      payments:
        'Настраиваем международные расчёты, валютный контроль и безопасные платежи. Помогаем снять блокировки.',
      analytics:
        'Проверяем партнёров, проводим Due Diligence и рыночную аналитику. Помогаем выйти на новые рынки.',
      other:
        'Сопровождаем выход на внешние рынки: локализация, партнёры, дистрибуция и Soft Landing.'
    };
    return descriptions[direction];
  },
  serviceCta:
    'Хотите подключить экспертов СРВТ? Оставьте заявку, и менеджер свяжется сегодня.',
  requestCaseText:
    'Опишите ситуацию, проект или проблему. Я быстро пойму направление и предложу решения.',
  caseAnalyzing: 'Секунду, анализирую ваш кейс...',
  caseAiResponse: (directionLabel: string, summary: string, advice: string): string =>
    `Я отнёс ваш кейс к направлению *${directionLabel}* и сверился с базой знаний СРВТ.\n\nКратко по ситуации:\n${summary}\n\nЧто можно сделать:\n${advice}`,
  caseCta: 'Передать кейс эксперту',
  caseClosing:
    'Ваш кейс выглядит значимым — здесь есть и риски, и возможности. Передать задачу в работу? Оставьте контакт, и профильный эксперт СРВТ вернётся с конкретными шагами.',
  leadFormName: 'Как к вам обращаться?',
  leadDataMissing:
    'Не получилось зафиксировать данные сценария. Запустите его, пожалуйста, ещё раз.',
  leadFormNamePrefilled: (name: string): string =>
    `Записал имя *${name}*. Если хотите указать другое — просто отправьте новое имя.`,
  leadFormContact:
    'Оставьте телефон или любой способ связи: @username, WhatsApp, Telegram, почту — что удобнее.',
  leadFormCompany: 'Компания или проект (по желанию). Можно написать «нет».',
  leadFormConfirm: (lead: LeadPayload): string =>
    `Проверьте заявку:\n• Имя: ${lead.name}\n• Контакт: ${lead.phone}\n• Компания: ${
      lead.company ?? 'не указано'
    }\nОтправляем менеджеру?`,
  leadFormIntroHot:
    'Понимаю, что задача требует срочного внимания. Оставьте контакт, и менеджер СРВТ вернётся в течение 15 минут с конкретными предложениями.',
  leadFormIntroWarm:
    'Оставьте удобный способ связи — мы подключим эксперта и подготовим рекомендации по вашему кейсу.',
  leadFormIntroCold:
    'Запишите, как с вами связаться. Мы аккуратно изучим запрос и вернёмся с вариантами, когда вам будет удобно.',
  leadFormSubmitted:
    'Спасибо! Передал контакт менеджеру СРВТ. Он свяжется в течение рабочего часа.',
  managerContact:
    'Заполните короткую форму, и персональный менеджер подключится в течение 15 минут.',
  subsidyIntro:
    'Рассчитаем субсидию. Ответьте на 5 вопросов — подберу программы СРВТ и регионов.',
  subsidyResult: (amount: number): string =>
    `По предварительному расчёту (на основе правил СРВТ) вам доступна субсидия до ${amount.toLocaleString(
      'ru-RU'
    )} ₽.`,
  subsidySummaryLead:
    (amount: number): string =>
      `Без заявки эти ${formatCurrency(amount)} так и останутся в бюджете. Передайте расчёт специалисту СРВТ — мы проверим, реально ли получить эту сумму и поможем собрать документы.`,
  subsidyNoMatch:
    'Пока нет готовых программ по этим параметрам, но эксперт может подобрать вручную. Оставьте контакт?',
  fallback:
    'Я показываю плиточное меню. Выберите сценарий, чтобы мы нашли решение быстрее.',
  leadFormValidationError:
    'Не похоже на способ связи. Напишите телефон, @username, ссылку на мессенджер или e-mail.',
  technicalIssue:
    'Сейчас наблюдаем небольшие технические сложности. Попробуйте ещё раз или оставьте заявку через меню — эксперт всё равно её увидит.'
};

export const getDirectionLabel = (direction: Direction): string => directionLabels[direction];

const scenarioLabels: Record<string, string> = {
  quiz_help: 'Квиз: Получить помощь',
  case_review: 'Проверка кейса',
  subsidy_application: 'Калькулятор субсидий',
  manager_contact: 'Связаться с менеджером'
};

export const formatLeadForManager = (lead: LeadPayload): string => {
  const scenarioLabel = formatScenarioLabel(lead.scenario);
  const directionLabel = getDirectionLabel(lead.direction);
  const scoreLine = typeof lead.score === 'number' ? `${lead.score}/5` : '—';
  const priorityLine = formatPriority(lead.score);
  const contextLines = buildContextLines(lead.metadata);

  return [
    '*[Новый лид из SRVT Assistant]*',
    '',
    `*Сценарий:* ${scenarioLabel}`,
    `*Направление:* ${directionLabel}`,
    `*Оценка:* ${scoreLine}`,
    `*Приоритет:* ${priorityLine}`,
    '',
    '*Клиент:*',
    `— Имя: ${lead.name}`,
    `— Контакт: ${lead.phone}`,
    `— Компания: ${lead.company ?? 'не указана'}`,
    `— Telegram ID: ${lead.userId}`,
    '',
    '*Контекст:*',
    contextLines.length ? contextLines.join('\n') : '— Нет дополнительных данных'
  ].join('\n');
};

const formatScenarioLabel = (scenario: string): string => {
  if (scenarioLabels[scenario]) {
    return scenarioLabels[scenario];
  }

  if (scenario.startsWith('service_')) {
    const [, directionKey] = scenario.split('_');
    if (directionKey && isDirection(directionKey)) {
      return `Услуги: ${directionLabels[directionKey]}`;
    }
    return 'Услуги СРВТ';
  }

  return `Сценарий: ${scenario}`;
};

const buildContextLines = (
  metadata?: Record<string, unknown>
): string[] => {
  if (!metadata) {
    return [];
  }

  const lines: string[] = [];
  const summary = metadata.summary;
  if (typeof summary === 'string' && summary.trim()) {
    lines.push(`— ${summary.trim()}`);
  }

  const advice = metadata.advice;
  if (typeof advice === 'string' && advice.trim()) {
    lines.push(`— Рекомендации: ${advice.trim()}`);
  }

  const service = metadata.service;
  if (typeof service === 'string' && service.trim()) {
    lines.push(`— Услуга: ${service.trim()}`);
  }

  const sources = metadata.sources;
  if (Array.isArray(sources) && sources.length) {
    lines.push(`— Источники базы СРВТ: ${sources.join(', ')}`);
  }

  const answers = metadata.answers;
  if (answers && typeof answers === 'object') {
    const values = Object.values(answers as Record<string, unknown>)
      .map((value) => (typeof value === 'string' ? value : undefined))
      .filter(Boolean) as string[];
    if (values.length) {
      lines.push(`— Детали запроса: ${values.join(', ')}`);
    }
  }

  const text = metadata.text;
  if (typeof text === 'string' && text.trim()) {
    lines.push(`— Текст кейса: ${truncate(text.trim(), 200)}`);
  }

  const input = metadata.input;
  if (input && typeof input === 'object' && !Array.isArray(input)) {
    const record = input as Record<string, unknown>;
    const details: string[] = [];
    if (typeof record.entityType === 'string') {
      details.push(`форма: ${record.entityType}`);
    }
    if (typeof record.costType === 'string') {
      details.push(`затраты: ${record.costType}`);
    }
    if (typeof record.spend === 'number') {
      details.push(`сумма: ${formatCurrency(record.spend)}`);
    }
    if (typeof record.hasExport === 'boolean') {
      details.push(`экспорт: ${record.hasExport ? 'да' : 'нет'}`);
    }
    if (typeof record.region === 'string') {
      details.push(`регион: ${record.region}`);
    }
    if (details.length) {
      lines.push(`— Параметры субсидии: ${details.join(', ')}`);
    }
  }

  if (typeof metadata.spendRangeLabel === 'string') {
    lines.push(`— Диапазон затрат: ${metadata.spendRangeLabel}`);
  }

  const results = metadata.results;
  if (Array.isArray(results) && results.length) {
    const titles = results
      .map((result) => {
        if (result && typeof result === 'object' && 'title' in result) {
          return String((result as Record<string, unknown>).title);
        }
        return undefined;
      })
      .filter(Boolean)
      .slice(0, 2) as string[];
    if (titles.length) {
      lines.push(`— Программы: ${titles.join(', ')}`);
    }
  }

  return lines;
};

const isDirection = (value: string): value is Direction =>
  (Object.keys(directionLabels) as Direction[]).includes(value as Direction);

const formatCurrency = (value: number): string =>
  `${Math.round(value).toLocaleString('ru-RU')} ₽`;

const truncate = (text: string, limit: number): string =>
  text.length > limit ? `${text.slice(0, limit)}…` : text;

const formatPriority = (score?: number): string => {
  if (typeof score !== 'number') {
    return '🌱 низкий';
  }
  if (score >= 4) {
    return '🔥 высокий';
  }
  if (score >= 2) {
    return '⚡ средний';
  }
  return '🌱 низкий';
};

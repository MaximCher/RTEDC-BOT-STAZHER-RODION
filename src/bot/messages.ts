import { Direction, LeadPayload, ConversationMetadata } from '../types/lead';
import {
  EstimatedProgram,
  SubsidyClassification,
  SubsidyCostType,
  SubsidyRegion,
  SubsidySector
} from '../types/subsidy';

const directionLabels: Record<Direction, string> = {
  finance: 'Финансирование',
  logistics: 'Логистика',
  payments: 'Платежи',
  analytics: 'Аналитика и проверка партнера',
  other: 'Другое направление'
};

const subsidySectorLabels: Record<SubsidySector, string> = {
  it: 'ИТ и цифровые продукты',
  export: 'Экспорт',
  manufacturing: 'Производство',
  logistics: 'Логистика и ВЭД',
  agro: 'АПК',
  tourism: 'Туризм',
  agrotourism: 'Агротуризм',
  services: 'Услуги',
  construction: 'Строительство',
  education: 'Образование',
  healthcare: 'Здравоохранение',
  other: 'Другие направления'
};

const subsidyCostTypeLabels: Record<SubsidyCostType, string> = {
  logistics: 'Логистика',
  marketing: 'Маркетинг / продвижение',
  certification: 'Сертификация и лицензии',
  equipment: 'Оборудование',
  staff: 'Персонал',
  payroll: 'ФОТ',
  r_and_d: 'R&D / разработка',
  exhibitions: 'Выставки и бизнес-миссии',
  software: 'Софт',
  training: 'Обучение',
  other: 'Прочие затраты'
};

const subsidyRegionLabels: Record<SubsidyRegion, string> = {
  moscow: 'Москва / МО',
  spb: 'Санкт-Петербург / ЛО',
  dfo: 'Дальний Восток',
  fo: 'Россия (фед. программы)',
  other: 'Другой регион',
  unknown: 'Регион не указан'
};

export const messages = {
  welcome: (name?: string): string =>
    `Привет${name ? `, ${name}` : ''}! Я SRVT Assistant 👋\n\nПомогаю бизнесу с финансированием, субсидиями, логистикой, платежами и проверкой контрагентов.\n\nВыберите, с чего начнём 👇`,
  mainMenuHint:
    'Главное меню: 🧭 подбор решения, 📋 услуги СРВТ, 👨‍💼 прямой контакт с экспертом.',
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
  servicesIntro:
    '📋 Услуги СРВТ: выберите задачу — и я сразу подскажу, как можем помочь и подключу эксперта.',
  serviceDescription: (direction: Direction): string => {
    const descriptions: Record<Direction, string> = {
      finance:
        '💰 Финансирование, субсидии и меры поддержки. Подберём программы, подготовим документы и доведём до выплаты.',
      logistics:
        '🚚 Логистика и ВЭД. Просчитаем маршруты, оптимизируем склады и поможем пройти таможню без задержек.',
      payments:
        '💳 Платежи и валютный контроль. Настроим расчёты, договоримся с банками, снимем ограничения и блокировки.',
      analytics:
        '🔍 Проверка контрагентов и аналитика. Due diligence, мониторинг рисков и поиск партнёров на целевых рынках.',
      other:
        '🌍 Выход на зарубежные рынки. Поможем адаптировать продукт, найти каналы сбыта и запустить продажи.'
    };
    return descriptions[direction];
  },
  serviceCta:
    '✍️ Оставьте заявку — подключим профильного эксперта и доведём задачу до результата.',
  solutionIntroText:
    '🧭 Подберём решение под вашу задачу. Опишите свободным текстом: что за бизнес, какие вопросы, суммы и сроки. После каждого ответа я задам уточняющий вопрос или предложу шаги.',
  solutionFallback:
    'Понимаю, что вопрос нестандартный. Напишите подробнее — я уточню детали и предложу варианты подключить экспертов СРВТ.',
  solutionAwaitHint:
    'Напишите ответ текстом ниже — я продолжу задавать уточняющие вопросы и соберу всё для передачи эксперту.',
  solutionTransferHint:
    'Чтобы передать этот кейс эксперту СРВТ, нажмите кнопку «📨 Отправить данные эксперту» ниже.',
  solutionAfterReady:
    'Кейс уже описан достаточно подробно. Чтобы эксперт СРВТ подготовил план и связался с вами, нажмите «📨 Отправить данные эксперту» ниже.',
  solutionWaitingInfo:
    'После отправки данных эксперт СРВТ свяжется в рабочее время (обычно от 1 до 3 рабочих дней).',
  solutionOffTopicShort:
    'Я помогаю по вопросам внешней торговли, финансирования, логистики, платежей и проверки контрагентов. Давайте вернёмся к вашему бизнес-вопросу 🙂',
  solutionOffTopicAsk:
    'Опишите, пожалуйста, рабочую задачу: что за бизнес, какие суммы и сроки, что сейчас мешает или волнует.',
  requestCaseText:
    '🧭 Подберём решение под вашу задачу.\n\nОпишите свободным текстом:\n— что за бизнес и рынок;\n— бюджеты/масштаб;\n— что болит или тормозит рост;\n— какой результат хотите.\n\nСверю вводные с базой знаний СРВТ и предложу план действий.',
  caseAnalyzing: 'Пару секунд, анализирую ваш кейс и сверяю с базой знаний СРВТ…',
  caseAiResponse: (
    directionLabel: string,
    summary: string,
    advice: string,
    riskLevel?: string,
    potentialValue?: string
  ): string => {
    const formattedAdvice = formatAdviceBullets(advice);
    const riskLine = formatRiskSummary(riskLevel, potentialValue);
    return [
      '🧭 *Предварительный разбор вашего кейса*',
      '',
      `*Направление:* ${directionLabel}`,
      riskLine ? `_${riskLine}_` : null,
      '',
      '*Ситуация:*',
      summary,
      '',
      '*Что предлагаем сделать:*',
      formattedAdvice,
      '',
      '_Это предварительный вывод по базе знаний СРВТ. Живой эксперт уточнит детали и подготовит конкретный план._'
    ]
      .filter(Boolean)
      .join('\n');
  },
  caseCta: '✍️ Передать кейс эксперту',
  caseClosing:
    'Если хотите, чтобы эксперт СРВТ взял кейс в работу, оставьте контакт. Подготовим конкретные варианты и проведём через бюрократию.',
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
    'Готово! Передал информацию эксперту СРВТ. Он свяжется в ближайшее рабочее время и пришлёт план действий.',
  managerContact:
    '🔥 Отличный выбор! Эксперт СРВТ возьмёт ваш кейс и предложит конкретный план. Оставьте удобный способ связи: телефон, @username или почту — напишем в ближайшее рабочее время.',
  subsidyIntroText:
    '💰 Проверим, можете ли вы получить субсидию.\n\nРасскажите коротко:\n— чем занимается компания и какие расходы хотите компенсировать;\n— примерный бюджет в рублях;\n— где зарегистрированы или ведёте деятельность.\n\nЧем точнее вводные, тем точнее расчёт.',
  subsidyAiHoldHint: 'Жду ваш ответ текстом ниже 👇',
  subsidyAiFallback:
    'Пока не удалось сформировать расчёт автоматически. Опишите расходы и регион ещё раз или сразу передайте данные эксперту — он проверит субсидии вручную.',
  subsidyNoProgramText:
    'По вашему запросу нет прямых программ субсидий, но есть альтернативные меры поддержки. Нажмите «Отправить данные эксперту» — команда СРВТ подберёт варианты и проведёт по заявке.',
  subsidyClarifyFallback:
    'Нужны ещё детали, чтобы подобрать субсидии. Напишите, какие расходы хотите компенсировать, примерную сумму и регион.',
  subsidyDefaultFollowUp:
    'Ваш кейс выглядит перспективно. Поделитесь, пожалуйста, где зарегистрирована компания и какие расходы хотите компенсировать — добавим эти данные в расчёт.',
  subsidyNeedFieldsHint:
    'Расскажите, пожалуйста, регион и примерный размер затрат — так быстрее доберёмся до конкретных программ.',
  subsidyManualEstimate:
    'Прямо сейчас нельзя честно озвучить сумму — не хватает пары вводных. Но кейс перспективный: нажмите «Отправить данные эксперту», и мы вручную подберём меры поддержки, чтобы не оставить деньги в бюджете.',
  subsidyManualEstimateSoft:
    'Чтобы не придумывать цифры из воздуха, лучше передать кейс эксперту. Он дособерёт документы и поможет получить компенсацию.',
  subsidyApproxEstimateIntro:
    'По вашим вводным уже можно прикинуть варианты. Ниже — предварительные меры поддержки, дальше эксперт поможет оформить заявку и подтвердить цифры.',
  subsidyEstimationDisclaimer:
    '⚠️ Это предварительный расчёт. Итоговый размер зависит от отбора и пакета документов.',
  subsidyEstimationCta:
    'Чтобы не оставить эти деньги в бюджете, нажмите «Отправить данные эксперту» — подключим команду СРВТ и доведём заявку до выплат.',
  subsidyBackPrompt:
    'Шаг откатил. Напишите уточнение, какая информация изменилась или что хотите скорректировать.',
  subsidyBackUnavailable: 'Пока некуда откатываться — давайте продолжим с текущих вводных.',
  subsidyBackOk: 'Возвращаюсь к предыдущему вопросу.',
  fallback:
    'Верну вас в главное меню. Можно подобрать решение, посмотреть услуги СРВТ или сразу связаться с экспертом.',
  leadFormValidationError:
    'Не похоже на способ связи. Напишите телефон, @username, ссылку на мессенджер или e-mail.',
  technicalIssue:
    'Сейчас наблюдаем небольшие технические сложности. Попробуйте ещё раз или оставьте заявку через меню — эксперт всё равно её увидит.',
  flowBackToMenu: 'Вы вернулись в главное меню. Чем могу помочь?'
};

export const getDirectionLabel = (direction: Direction): string => directionLabels[direction];

const scenarioLabels: Record<string, string> = {
  solution_case: 'Подбор решения',
  quiz_help: 'Квиз: Получить помощь',
  subsidy_application: 'Калькулятор субсидий',
  manager_contact: 'Связаться с экспертом'
};

export const formatLeadForManager = (lead: LeadPayload): string => {
  const scenarioLabel = getScenarioLabel(lead.scenario);
  const directionLabel = getDirectionLabel(lead.direction);
  const scoreLine = typeof lead.score === 'number' ? `${lead.score}/5` : '—';
  const priorityLine = formatPriority(lead.score);
  const contextLines = buildContextLines(lead.metadata);
  const solutionBlocks = buildSolutionBlocks(lead.metadata);

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
    contextLines.length ? contextLines.join('\n') : '— Нет дополнительных данных',
    ...solutionBlocks,
    ...buildSubsidyBlocks(lead.metadata)
  ].join('\n');
};

const TELEGRAM_MESSAGE_LIMIT = 3500;

export const formatSubsidyEstimationForUser = (
  programs: EstimatedProgram[],
  classification: SubsidyClassification,
  hasAmountEstimate: boolean
): string => {
  if (!hasAmountEstimate || !programs.length) {
    return [
      messages.subsidyManualEstimate,
      '',
      messages.subsidyEstimationDisclaimer
    ].join('\n');
  }

  const positiveAmounts = programs
    .map((program) => program.estimatedAmount)
    .filter((value) => value > 0);
  const maxAmount = Math.max(...positiveAmounts, 0);
  const minAmount = Math.min(...positiveAmounts, maxAmount);

  const header = `💰 Предварительный расчёт: до ${formatCurrency(maxAmount)} по ${programs.length} программам поддержки`;
  const confident =
    classification.costTypes.length > 0 &&
    ((classification.budgetTo ?? classification.budgetFrom ?? 0) > 0);
  const rangeLine =
    minAmount && minAmount !== maxAmount
      ? `Ориентировочно можно рассчитывать на ${formatCurrency(minAmount)}–${formatCurrency(
          maxAmount
        )}.`
      : `Ориентировочно можно рассчитывать до ${formatCurrency(maxAmount)}.`;

  const summaryLine = confident
    ? `По вашим вводным субсидия выглядит очень реалистично. ${rangeLine}`
    : `По вашим вводным субсидия возможна. ${rangeLine}`;

  const profileBlock = buildSubsidyProfileBlock(classification);

  const listIntro = 'Топ программ:';
  const items = programs.slice(0, 3).map((program, index) => {
    const coverage =
      typeof program.coveragePercent === 'number' ? ` (до ${program.coveragePercent}%)` : '';
    const description = program.description ? `\n   ${truncate(program.description, 120)}` : '';
    return `${index + 1}) ${truncate(program.title, 90)} — до ${formatCurrency(
      program.estimatedAmount
    )}${coverage}${description}`;
  });

  const footer = [messages.subsidyEstimationDisclaimer, messages.subsidyEstimationCta]
    .filter(Boolean)
    .join('\n');

  const lines = [header, '', summaryLine, profileBlock, '', listIntro, ...items, '', footer].filter(
    Boolean
  ) as string[];

  return squeezeToTelegramLimit(lines);
};

const buildSubsidyProfileBlock = (classification: SubsidyClassification): string => {
  const lines: string[] = [];
  if (classification.sectors.length) {
    const primary = classification.sectors[0];
    lines.push(`• Сектор: ${subsidySectorLabels[primary] ?? primary}`);
  }
  lines.push(`• Регион: ${formatSubsidyRegionLabel(classification.region)}`);

  const budgetLabel = formatBudgetRange(classification.budgetFrom, classification.budgetTo);
  if (budgetLabel) {
    lines.push(`• Бюджет: ${budgetLabel}`);
  }

  lines.push(`• Экспорт: ${formatExportStatus(classification.export)}`);

  if (classification.costTypes.length) {
    const costLabels = classification.costTypes
      .map((type) => subsidyCostTypeLabels[type] ?? type)
      .join(', ');
    lines.push(`• Затраты: ${costLabels}`);
  }

  return lines.length ? ['Профиль кейса:', ...lines].join('\n') : '';
};

const squeezeToTelegramLimit = (lines: string[]): string => {
  const text = lines.join('\n');
  if (text.length <= TELEGRAM_MESSAGE_LIMIT) {
    return text;
  }
  return `${text.slice(0, TELEGRAM_MESSAGE_LIMIT - 1)}…`;
};

export const getScenarioLabel = (scenario: string): string => {
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

  const riskLevel = metadata.riskLevel;
  if (typeof riskLevel === 'string') {
    lines.push(`— Риск: ${formatLevelValue(riskLevel, riskLevelLabels)}`);
  }

  const potentialValue = metadata.potentialValue;
  if (typeof potentialValue === 'string') {
    lines.push(`— Потенциал: ${formatLevelValue(potentialValue, potentialLevelLabels)}`);
  }

  const kbUsed = metadata.kbUsed;
  if (typeof kbUsed === 'boolean') {
    lines.push(`— База знаний СРВТ: ${kbUsed ? 'использована' : 'не задействована'}`);
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
          const record = result as Record<string, unknown>;
          const title = typeof record.title === 'string' ? record.title : undefined;
          const code =
            typeof record.programCode === 'string' ? record.programCode.toUpperCase() : undefined;
          if (title) {
            return code ? `${code}: ${title}` : title;
          }
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

const buildSolutionBlocks = (
  metadata?: (Record<string, unknown> & ConversationMetadata) | undefined
): string[] => {
  if (!metadata) {
    return [];
  }

  const blocks: string[] = [];
  const managerSummary = metadata.solutionManagerSummary;
  if (typeof managerSummary === 'string' && managerSummary.trim()) {
    blocks.push('', '*Резюме от ассистента:*', managerSummary.trim());
  }

  const dialog = metadata.solutionDialog;
  if (Array.isArray(dialog) && dialog.length) {
    blocks.push('', '*История диалога с ботом:*');
    const lastTurns = dialog.slice(-6);
    for (const turn of lastTurns) {
      const prefix = turn.role === 'assistant' ? 'Бот' : 'Клиент';
      blocks.push(`— ${prefix}: ${turn.text}`);
    }
    if (dialog.length > lastTurns.length) {
      blocks.push('— … (остальные реплики сохранены в системе)');
    }
  }

  return blocks;
};

const buildSubsidyBlocks = (metadata?: Record<string, unknown>): string[] => {
  if (!metadata) {
    return [];
  }

  const blocks: string[] = [];
  const root = metadata.subsidy as
    | {
        classification?: SubsidyClassification;
        programs?: EstimatedProgram[];
        hasAmountEstimate?: boolean;
        dialog?: { role?: string; text: string }[];
      }
    | undefined;
  const classification =
    (metadata.subsidyClassification as SubsidyClassification | undefined) ?? root?.classification;
  const programs =
    (metadata.subsidyPrograms as EstimatedProgram[] | undefined) ?? root?.programs;
  const dialog =
    (metadata.subsidyDialog as { role?: string; text: string }[] | undefined) ?? root?.dialog;
  const hasAmountEstimate =
    typeof metadata.hasAmountEstimate === 'boolean'
      ? metadata.hasAmountEstimate
      : typeof root?.hasAmountEstimate === 'boolean'
        ? root.hasAmountEstimate
        : Boolean(programs?.some((program) => program.estimatedAmount > 0));

  if (classification) {
    blocks.push('', '*Субсидии:*');
    const regionLabel = formatSubsidyRegionLabel(classification.region);
    const costTypes = classification.costTypes
      .map((type) => subsidyCostTypeLabels[type] ?? type)
      .join(', ');
    const budgetLabel = formatBudgetRange(classification.budgetFrom, classification.budgetTo);
    const details: Array<string | undefined> = [
      classification.sectors.length
        ? `— Сектор: ${subsidySectorLabels[classification.sectors[0]] ?? classification.sectors[0]}`
        : undefined,
      `— Экспорт: ${formatExportStatus(classification.export)}`,
      `— Регион: ${regionLabel}`,
      budgetLabel ? `— Бюджет: ${budgetLabel}` : undefined,
      costTypes ? `— Затраты: ${costTypes}` : undefined,
      classification.notes ? `— Заметки: ${truncate(classification.notes, 120)}` : undefined
    ];
    blocks.push(...(details.filter(Boolean) as string[]));
  }

  if (classification) {
    const estimationPreview = formatSubsidyEstimationForUser(
      programs ?? [],
      classification,
      hasAmountEstimate
    );
    blocks.push('', '*Ответ бота пользователю:*', estimationPreview);
  }

  if (programs?.length) {
    blocks.push('', '*Подобранные программы:*');
    programs.slice(0, 3).forEach((program, index) => {
      blocks.push(
        `${index + 1}) ${truncate(program.title, 70)} (до ${formatCurrency(program.estimatedAmount)})`
      );
    });
  }

  if (dialog?.length) {
    blocks.push('', '*Диалог (фрагмент):*');
    dialog.slice(-4).forEach((turn) => {
      const prefix = turn.role === 'assistant' ? 'SRVT AI' : 'Клиент';
      blocks.push(`— ${prefix}: ${turn.text}`);
    });
  }

  return blocks;
};

const formatSubsidyRegionLabel = (region: SubsidyRegion): string =>
  subsidyRegionLabels[region] ?? subsidyRegionLabels.other;

const formatBudgetRange = (min?: number | null, max?: number | null): string | undefined => {
  if (typeof min === 'number' && typeof max === 'number' && min > 0 && max > 0) {
    if (min === max) {
      return formatCurrency(max);
    }
    return `${formatCurrency(min)}–${formatCurrency(max)}`;
  }
  if (typeof min === 'number' && min > 0) {
    return `от ${formatCurrency(min)}`;
  }
  if (typeof max === 'number' && max > 0) {
    return `до ${formatCurrency(max)}`;
  }
  return undefined;
};

const formatExportStatus = (value: boolean | null | undefined): string => {
  if (value === true) {
    return 'да';
  }
  if (value === false) {
    return 'нет';
  }
  return 'не указано';
};

const formatAdviceBullets = (advice: string): string => {
  const rawLines = advice
    .split(/[\n•\-]+/)
    .map((line) => line.replace(/^[•\-\s]+/, '').trim())
    .filter(Boolean);

  const selected = rawLines.length ? rawLines.slice(0, 4) : [advice.trim()];

  return selected.map((line) => `• ${line}`).join('\n');
};

const isDirection = (value: string): value is Direction =>
  (Object.keys(directionLabels) as Direction[]).includes(value as Direction);

const riskLevelLabels: Record<string, string> = {
  low: 'низкий',
  medium: 'средний',
  high: 'высокий'
};

const potentialLevelLabels: Record<string, string> = {
  low: 'ограниченный',
  medium: 'заметный',
  high: 'высокий'
};

const formatRiskSummary = (
  riskLevel?: string,
  potentialValue?: string
): string | undefined => {
  const riskText = riskLevel
    ? `риск ${formatLevelValue(riskLevel, riskLevelLabels)}`
    : undefined;
  const potentialText = potentialValue
    ? `потенциал ${formatLevelValue(potentialValue, potentialLevelLabels)}`
    : undefined;
  const parts = [riskText, potentialText].filter(Boolean);
  return parts.length ? parts.join(' · ') : undefined;
};

const formatLevelValue = (
  value: string,
  dictionary: Record<string, string>
): string => dictionary[value] ?? value;

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

import { Direction, LeadPayload, ConversationMetadata } from '../types/lead';
import {
  EstimatedProgram,
  SubsidyClassification,
  SubsidyCostType,
  SubsidyRegion,
  SubsidySector
} from '../types/subsidy';
import { escapeMarkdown } from '../utils/text';

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
    '📋 Услуги СРВТ. Выберите нужное направление — расскажу, как подключим экспертов и быстро доведём задачу до результата.',
  serviceScenarioInitialPrompt:
    'Расскажите свободным текстом: чем занимаетесь, какой объём или сумму нужно закрыть и к каким срокам. После первого ответа уточню один нюанс и предложу шаги.',
  serviceScenarioClarifyIntro:
    'Спасибо, картина понятна. Чтобы предложить точный формат, ответьте ещё на один вопрос:',
  serviceScenarioReady:
    'Отлично, вводных хватит. Нажмите «📝 Отправить данные эксперту», и команда СРВТ подготовит решение и вернётся с предложением.',
  serviceScenarioReadyReminder:
    'Если готовы передать кейс, просто нажмите «📝 Отправить данные эксперту» — остальное возьмём на себя.',
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
  clubApplicationIntro:
    '🤝 *Клуб экспортёров и импортёров СРВТ.РФ*\n\nЗакрытое сообщество действующих ВЭД-команд: доступ к проверенным поставщикам и покупателям, совместные закупки, разблокированные маршруты логистики, ежемесячные сессии с экспертами и быстрый обмен новыми схемами. Оставьте контакт — менеджер свяжется в течение 15 минут, расскажет условия и проверит, как ваш бизнес впишется в клуб.',
  academyApplicationIntro:
    '🎓 *Академия СРВТ.РФ*\n\nПрактические программы по выходу на экспорт, международной логистике, платежам и получению мер поддержки. Кураторы из СРВТ помогают собирать документы, адаптировать маркетинг под зарубеж и сопровождают до результата. Подайте заявку — перезвоним в течение 15 минут, подберём курс и подключим наставника под ваши цели.',
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
  manager_contact: 'Связаться с экспертом',
  club_application: 'Клуб экспортёров и импортёров',
  academy_application: 'Академия СРВТ.РФ',
  service_international_transactions: 'Услуги: Международные транзакции',
  service_loans: 'Услуги: Льготные кредиты',
  service_logistics: 'Услуги: Международная логистика',
  service_negotiations: 'Услуги: Сопровождение переговоров',
  service_translations: 'Услуги: Лингвистические переводы',
  service_analytics: 'Услуги: Аналитика ВЭД и проверка контрагентов'
};

export const formatLeadForManager = (lead: LeadPayload): string => {
  const scenarioLabel = escapeMarkdown(getScenarioLabel(lead.scenario));
  const directionLabel = escapeMarkdown(getDirectionLabel(lead.direction));
  const scoreLine = escapeMarkdown(typeof lead.score === 'number' ? `${lead.score}/5` : '—');
  const priorityLine = escapeMarkdown(formatPriority(lead.score));
  const safeName = sanitizeText(lead.name) ?? escapeMarkdown('не указано');
  const safePhone = sanitizeText(lead.phone) ?? escapeMarkdown('не указан');
  const safeCompany = sanitizeText(lead.company) ?? escapeMarkdown('не указана');
  const safeUserId = escapeMarkdown(
    lead.userId !== undefined && lead.userId !== null ? String(lead.userId) : 'не указан'
  );
  const contextLines = buildContextLines(lead.metadata);
  const serviceBlocks = buildServiceBlocks(lead.metadata);
  const solutionBlocks = buildSolutionBlocks(lead.metadata);
  const subsidyBlocks = buildSubsidyBlocks(lead.metadata);

  return [
    '*[Новый лид из SRVT Assistant]*',
    '',
    `*Сценарий:* ${scenarioLabel}`,
    `*Направление:* ${directionLabel}`,
    `*Оценка:* ${scoreLine}`,
    `*Приоритет:* ${priorityLine}`,
    '',
    '*Клиент:*',
    `— Имя: ${safeName}`,
    `— Контакт: ${safePhone}`,
    `— Компания: ${safeCompany}`,
    `— Telegram ID: ${safeUserId}`,
    '',
    '*Контекст:*',
    contextLines.length ? contextLines.join('\n') : '— Нет дополнительных данных',
    ...serviceBlocks,
    ...solutionBlocks,
    ...subsidyBlocks
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

export const getScenarioLabel = (scenario: string): string =>
  scenarioLabels[scenario] ?? `Сценарий: ${scenario}`;

const buildContextLines = (metadata?: Record<string, unknown>): string[] => {
  if (!metadata) {
    return [];
  }

  const lines: string[] = [];

  const summaryText = sanitizeText(metadata.summary);
  if (summaryText) {
    lines.push(`— ${summaryText}`);
  }

  const adviceText = sanitizeText(metadata.advice);
  if (adviceText) {
    lines.push(`— Рекомендации: ${adviceText}`);
  }

  const serviceText = sanitizeText(metadata.service);
  if (serviceText) {
    lines.push(`— Услуга: ${serviceText}`);
  }

  const sources = Array.isArray(metadata.sources) ? metadata.sources : undefined;
  if (sources?.length) {
    const formattedSources = sources
      .map((source) => sanitizeText(source))
      .filter(Boolean) as string[];
    if (formattedSources.length) {
      lines.push(`— Источники базы СРВТ: ${formattedSources.join(', ')}`);
    }
  }

  if (typeof metadata.riskLevel === 'string') {
    const riskLabel = sanitizeText(formatLevelValue(metadata.riskLevel, riskLevelLabels));
    if (riskLabel) {
      lines.push(`— Риск: ${riskLabel}`);
    }
  }

  if (typeof metadata.potentialValue === 'string') {
    const potentialLabel = sanitizeText(
      formatLevelValue(metadata.potentialValue, potentialLevelLabels)
    );
    if (potentialLabel) {
      lines.push(`— Потенциал: ${potentialLabel}`);
    }
  }

  if (typeof metadata.kbUsed === 'boolean') {
    const knowledgeStatus = metadata.kbUsed ? 'использована' : 'не задействована';
    lines.push(`— База знаний СРВТ: ${escapeMarkdown(knowledgeStatus)}`);
  }

  const answers = metadata.answers;
  if (answers && typeof answers === 'object') {
    const values = Object.values(answers as Record<string, unknown>)
      .map((value) => sanitizeText(value))
      .filter(Boolean) as string[];
    if (values.length) {
      lines.push(`— Детали запроса: ${values.join(', ')}`);
    }
  }

  if (typeof metadata.text === 'string' && metadata.text.trim()) {
    const caseText = sanitizeText(truncate(metadata.text.trim(), 200));
    if (caseText) {
      lines.push(`— Текст кейса: ${caseText}`);
    }
  }

  const input = metadata.input;
  if (input && typeof input === 'object' && !Array.isArray(input)) {
    const record = input as Record<string, unknown>;
    const details: string[] = [];
    const entityType = sanitizeText(record.entityType);
    if (entityType) {
      details.push(`форма: ${entityType}`);
    }
    const costType = sanitizeText(record.costType);
    if (costType) {
      details.push(`затраты: ${costType}`);
    }
    if (typeof record.spend === 'number') {
      details.push(`сумма: ${escapeMarkdown(formatCurrency(record.spend))}`);
    }
    if (typeof record.hasExport === 'boolean') {
      details.push(`экспорт: ${escapeMarkdown(record.hasExport ? 'да' : 'нет')}`);
    }
    const region = sanitizeText(record.region);
    if (region) {
      details.push(`регион: ${region}`);
    }
    if (details.length) {
      lines.push(`— Параметры субсидии: ${details.join(', ')}`);
    }
  }

  const spendRange = sanitizeText(metadata.spendRangeLabel);
  if (spendRange) {
    lines.push(`— Диапазон затрат: ${spendRange}`);
  }

  const results = metadata.results;
  if (Array.isArray(results) && results.length) {
    const titles = results
      .map((result) => {
        if (result && typeof result === 'object' && 'title' in result) {
          const record = result as Record<string, unknown>;
          const title = sanitizeText(record.title);
          const code =
            typeof record.programCode === 'string'
              ? escapeMarkdown(record.programCode.toUpperCase())
              : undefined;
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

const buildServiceBlocks = (metadata?: Record<string, unknown>): string[] => {
  if (!metadata) {
    return [];
  }

  const type = sanitizeText(metadata.serviceType);
  const offer = sanitizeText(metadata.serviceOffer);
  const firstInput =
    typeof metadata.serviceFirstInput === 'string'
      ? sanitizeText(truncate(metadata.serviceFirstInput, 200))
      : undefined;
  const clarification =
    typeof metadata.serviceClarification === 'string'
      ? sanitizeText(truncate(metadata.serviceClarification, 200))
      : undefined;
  const question = sanitizeText(metadata.serviceClarifyQuestion);
  const dialog =
    Array.isArray(metadata.serviceDialog) && metadata.serviceDialog.length
      ? (metadata.serviceDialog as { role?: string; text: string }[])
      : undefined;

  if (!type && !offer && !firstInput && !clarification && !question && !dialog) {
    return [];
  }

  const blocks: string[] = ['', '*Услуга СРВТ:*'];
  if (type) {
    blocks.push(`Тип услуги: ${type}`);
  }
  if (firstInput || clarification) {
    blocks.push('Ответы клиента:');
    if (firstInput) {
      blocks.push(`— первый ввод: ${firstInput}`);
    }
    if (clarification) {
      blocks.push(`— уточняющий ответ: ${clarification}`);
    }
  }
  if (offer) {
    blocks.push(`Оффер: ${offer}`);
  }
  if (question) {
    blocks.push(`Уточняющий вопрос: ${question}`);
  }
  if (dialog?.length) {
    blocks.push('Диалог (фрагмент):');
    dialog.slice(-4).forEach((turn) => {
      const prefix = turn.role === 'assistant' ? 'SRVT' : 'Клиент';
      const turnText = sanitizeText(turn.text);
      if (turnText) {
        blocks.push(`— ${prefix}: ${turnText}`);
      }
    });
  }
  return blocks;
};

const buildSolutionBlocks = (
  metadata?: (Record<string, unknown> & ConversationMetadata) | undefined
): string[] => {
  if (!metadata) {
    return [];
  }

  const blocks: string[] = [];
  const managerSummary = metadata.solutionManagerSummary;
  const summaryText = sanitizeText(managerSummary);
  if (summaryText) {
    blocks.push('', '*Резюме от ассистента:*', summaryText);
  }

  const dialog = metadata.solutionDialog;
  if (Array.isArray(dialog) && dialog.length) {
    blocks.push('', '*История диалога с ботом:*');
    const lastTurns = dialog.slice(-6);
    for (const turn of lastTurns) {
      const prefix = turn.role === 'assistant' ? 'Бот' : 'Клиент';
      const turnText = sanitizeText(turn.text);
      if (turnText) {
        blocks.push(`— ${prefix}: ${turnText}`);
      }
    }
    if (dialog.length > lastTurns.length) {
      blocks.push('— … остальные реплики сохранены в системе');
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
    const regionLabel = escapeMarkdown(formatSubsidyRegionLabel(classification.region));
    const costTypes = classification.costTypes
      .map((type) => escapeMarkdown(subsidyCostTypeLabels[type] ?? type))
      .join(', ');
    const budgetLabel = formatBudgetRange(classification.budgetFrom, classification.budgetTo);
    const budgetText = budgetLabel ? escapeMarkdown(budgetLabel) : undefined;
    const sectorText = classification.sectors.length
      ? escapeMarkdown(subsidySectorLabels[classification.sectors[0]] ?? classification.sectors[0])
      : undefined;
    const notes = classification.notes
      ? sanitizeText(truncate(classification.notes, 120))
      : undefined;

    const details: Array<string | undefined> = [
      sectorText ? `— Сектор: ${sectorText}` : undefined,
      `— Экспорт: ${escapeMarkdown(formatExportStatus(classification.export))}`,
      `— Регион: ${regionLabel}`,
      budgetText ? `— Бюджет: ${budgetText}` : undefined,
      costTypes ? `— Затраты: ${costTypes}` : undefined,
      notes ? `— Заметки: ${notes}` : undefined
    ];
    blocks.push(...(details.filter(Boolean) as string[]));
  }

  if (classification) {
    const estimationPreview = formatSubsidyEstimationForUser(
      programs ?? [],
      classification,
      hasAmountEstimate
    );
    blocks.push('', '*Ответ бота пользователю:*', escapeMarkdown(estimationPreview));
  }

  if (programs?.length) {
    blocks.push('', '*Подобранные программы:*');
    programs.slice(0, 3).forEach((program, index) => {
      const title = sanitizeText(truncate(program.title, 70));
      const amount = escapeMarkdown(formatCurrency(program.estimatedAmount));
      if (title) {
        blocks.push(`${index + 1}) ${title} (до ${amount})`);
      }
    });
  }

  if (dialog?.length) {
    blocks.push('', '*Диалог (фрагмент):*');
    dialog.slice(-4).forEach((turn) => {
      const prefix = turn.role === 'assistant' ? 'SRVT AI' : 'Клиент';
      const turnText = sanitizeText(turn.text);
      if (turnText) {
        blocks.push(`— ${prefix}: ${turnText}`);
      }
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

const sanitizeText = (value: unknown): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? escapeMarkdown(trimmed) : undefined;
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

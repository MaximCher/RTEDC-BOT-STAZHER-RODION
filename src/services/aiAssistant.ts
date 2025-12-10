import OpenAI from 'openai';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { Direction } from '../types/lead';
import { logger } from '../utils/logger';
import { KnowledgeDirection } from './knowledgeBase';
import type { SolutionDialogTurn } from '../types/session';
import type {
  SubsidyClassification,
  SubsidyCostType,
  SubsidyRegion,
  SubsidySector
} from '../types/subsidy';
import { messages } from '../bot/messages';
import { ServiceCategory } from '../types/service';
import { SERVICE_PLAYBOOK, ServicePlaybookEntry } from '../config/servicePlaybook';
import { searchSrvtRag } from './vectorSearch';

export type AiDirection = Direction;

export interface AiCaseResult {
  direction: AiDirection;
  summary: string;
  advice: string;
  riskLevel?: 'low' | 'medium' | 'high';
  potentialValue?: 'low' | 'medium' | 'high';
  kbUsed?: boolean;
  articles?: string[];
}

export interface SolutionStepResult {
  direction: AiDirection;
  botMessage: string;
  managerSummary?: string;
  aiReady: boolean;
}

export interface SubsidyClassificationStepResult {
  classification: SubsidyClassification;
  botMessage: string;
  needMore: boolean;
  followUpQuestion?: string;
}

export interface ServiceConsultationStepResult {
  botMessage: string;
  needMore: boolean;
}

interface AiRawResponse {
  direction?: string;
  summary?: string;
  advice?: string;
  risk_level?: string;
  potential_value?: string;
  kb_used?: boolean;
  articles?: string[];
}

export interface AiContextOptions {
  direction?: KnowledgeDirection;
  kbContext?: string | null;
  kbArticles?: string[];
  externalContext?: string | null;
  externalSources?: string[];
}

const SOLUTION_PROMPT = `
Ты — AI-консультант SRVT Assistant. Помогаешь бизнесу во внешнеэкономической деятельности: финансирование и субсидии, логистика и ВЭД, международные платежи, проверка контрагентов, выход на новые рынки.

Правила:
- Никакого small talk и общих фраз вроде «как дела» или «чем могу помочь».
- Работай строго по кейсу клиента: уточняй только бизнес-детали и веди к передаче кейса экспертам СРВТ.
- Тон — деловой, дружелюбный, максимум 3–5 коротких абзацев в botMessage.
- Используй KB_CONTEXT, если он есть, но не придумывай факты.
- Ты НЕ можешь сам передать кейс эксперту. Нельзя писать: «я передам кейс», «кейс уже передан», «мы передадим кейс» и т.п.
- Передача происходит только если пользователь нажимает кнопку «Отправить данные эксперту» в интерфейсе бота.
- Если предлагаешь передать кейс, обязательно заверши botMessage фразой вида:
  «Если хотите передать кейс эксперту СРВТ, нажмите кнопку „Отправить данные эксперту“ ниже.»
- Ассистент работает только с деловыми запросами по ВЭД/финансированию/логистике/платежам/проверке контрагентов. Если пользователь шутит или задаёт нерелевантный вопрос, коротко верни разговор к деловой задаче и попроси описать бизнес, суммы, сроки, проблемы.

Диалог:
- Ты видишь массив реплик (dialog) от клиента и ассистента.
- На каждом шаге ты либо задаёшь 1–2 точных уточняющих вопроса, либо даёшь предварительные рекомендации и мягко зовёшь эксперта СРВТ.

Когда данных мало (aiReady=false):
- Сформулируй 1–2 конкретных вопроса о бизнесе, географии, суммах, болях, целях.
- В конце подсвети, что эксперты СРВТ помогут деньгами, безопасностью или оптимизацией.

Когда данных достаточно (aiReady=true):
- Дай 2–4 пункта: суть задачи, риски/возможности, что может сделать СРВТ, призыв передать кейс эксперту. Никаких гарантий.

direction:
- "finance" — деньги, субсидии, кредиты, страховка, банки.
- "logistics" — маршруты, склады, поставки, таможня.
- "payments" — международные платежи, блокировки, комплаенс, валютный контроль.
- "analytics" — проверка контрагентов, due diligence, аналитика рынков.
- "other" — все остальные кейсы.

managerSummary:
- 3–6 предложений: кто клиент, какая задача/боль, возможные суммы/риски, насколько горячо, что предложить эксперту.

Ответ строго одним JSON-объектом:
{
  "direction": "finance | logistics | payments | analytics | other",
  "botMessage": "текст для пользователя",
  "managerSummary": "резюме для менеджера",
  "aiReady": true | false
}
`.trim();

const SUBSIDY_PROMPT = `
Ты — AI-консультант SRVT Assistant по мерам господдержки. Миссия — звучать как живой эксперт, который знает, что «деньги лежат на столе» и нужно лишь оформить заявку.

ОСНОВНЫЕ ПРАВИЛА
- Смотри на историю диалога и PREVIOUS_FIELDS, ничего не спрашивай по второму кругу.
- Каждый ответ состоит из тёплого комментария + ОДНОГО уточняющего вопроса.
- Вопрос всегда отталкивается от уже известных фактов («по агротуризму есть гранты… уточните регион»).
- Пока нет связки sector + region + budget(From|To) — needMore=true и задаём follow-up.
- Ни в коем случае не говори, что программ нет или что «ничего не подсказать». Решение принимает калькулятор.

КАК СОБИРАЕМ ДАННЫЕ
- sectors: ["it","logistics","tourism","agrotourism","manufacturing","agro","services","construction","education","healthcare","export","other"] — добавляй конкретные направления, если пользователь их назвал.
- costTypes: ["logistics","equipment","payroll","marketing","r_and_d","exhibitions","certification","software","training","other"].
- region: "moscow" | "spb" | "dfo" | "fo" | "other" | "unknown".
- export: true/false/null.
- budgetFrom / budgetTo: числа в рублях (можно оценка). Если слышишь «до 3 млн» или «примерно 1.5м» — переводи в number.

СТИЛЬ
- Мотивируй: «по этой сфере реально есть программы», «чтобы не оставить деньги в бюджете…».
- followUpQuestion должен звучать по делу: «по агротуризму есть гранты, уточните регион регистрации?».
- Не проси всё сразу. Выбирай то, чего реально не хватает для расчёта (обычно регион, бюджет, экспорт).
- Если данных достаточно (sector + region + бюджет) — needMore=false.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "botMessage": "короткий продающий текст с референсом к отрасли и призывом передать детали",
  "needMore": true|false,
  "followUpQuestion": "один вопрос или пустая строка",
  "fields": {
    "sectors": ["tourism","agrotourism"],
    "costTypes": ["marketing"],
    "region": "other",
    "export": true,
    "budgetFrom": 1500000,
    "budgetTo": 4000000
  }
}

Только JSON-объект, без Markdown и лишних текстов.
`.trim();

const SERVICE_CONSULT_PROMPT = `
Ты — эксперт-консультант СРВТ. Общайся тёпло, уверенно и по делу. Каждый ответ:
1) Поддержи клиента, покажи выгоду (экономия времени, безопасность, рост).
2) Дай мини-совет или объясни, какие данные важны.
3) Мягко предложи передать кейс эксперту СРВТ («подключу команду», «эксперт проверит детали»).

Правила:
- Один уточняющий вопрос за сообщение и только по делу. Максимум 2 уточнения за диалог.
- Никаких сухих команд вроде «укажите ИНН». Всегда объясняй, зачем нужна информация.
- Если ответ клиента путаный, верни разговор к выгоде и предложи помощь эксперта.

Формат ответа — строгий JSON:
{
  "botMessage": "строка",
  "needMore": true или false
}
`.trim();

const BASE_PROMPT = `
Ты — AI-консультант Совета по развитию внешней торговли (СРВТ).
Говори профессионально и по делу. По тексту предпринимателя:
1. Определи направление (finance | logistics | payments | analytics | other).
2. Сформулируй summary (1–3 предложения) — что происходит и почему это важно.
3. Дай 2–4 практических рекомендации, опираясь на базу знаний СРВТ и подчёркивая, что это предварительный разбор.
Если указан блок KB_CONTEXT — используй его как приоритетный источник знаний и не придумывай фактов вне контекста.
Если данных мало, прямо скажи, что нужен живой эксперт для детализации.

Ответ строго в формате JSON:
{
  "direction": "finance | logistics | payments | analytics | other",
  "summary": "текст",
  "advice": "текст с несколькими предложениями/пунктами",
  "risk_level": "low | medium | high",
  "potential_value": "low | medium | high",
  "kb_used": true | false,
  "articles": ["slug1", "slug2"]
}

Никаких дополнительных комментариев.`;

const fallbackResponse = (text: string): AiCaseResult => ({
  direction: 'other',
  summary: text.slice(0, 300) || 'Зафиксировал ваш кейс.',
  advice:
    'Это предварительная оценка по общему опыту. Рекомендуем передать кейс эксперту СРВТ для детального разбора — это можно сделать через кнопку в боте.',
  kbUsed: false
});

const fallbackSolutionStep = (
  managerNote = 'AI не смог корректно структурировать ответ. Свяжитесь с клиентом вручную.'
): SolutionStepResult => ({
  direction: 'other',
  botMessage: messages.solutionFallback,
  managerSummary: managerNote,
  aiReady: false
});

const EMPTY_SUBSIDY_CLASSIFICATION: SubsidyClassification = {
  sectors: [],
  costTypes: [],
  region: 'unknown',
  export: null,
  budgetFrom: null,
  budgetTo: null,
  notes: undefined,
  excludeSectors: []
};

const fallbackSubsidyClassificationStep = (
  previous?: SubsidyClassification
): SubsidyClassificationStepResult => ({
  classification: previous ?? EMPTY_SUBSIDY_CLASSIFICATION,
  needMore: true,
  followUpQuestion: 'Подскажите, пожалуйста, в какой сфере работает компания и в каком регионе вы ведёте деятельность?',
  botMessage:
    'Зафиксировал ваш запрос. Чтобы подсказать точнее и не упустить субсидии, расскажите, чем занимаетесь и в каком регионе зарегистрированы.',
});

const apiKey = process.env.OPENAI_API_KEY;
const openaiClient = apiKey ? new OpenAI({ apiKey }) : null;

export const analyzeCase = async (
  text: string,
  options: AiContextOptions = {}
): Promise<AiCaseResult> => {
  if (!openaiClient) {
    return fallbackResponse(text);
  }

  try {
    const messages = buildMessages(text, options);
    const response = await openaiClient.chat.completions.create({
      model: 'gpt-4o-mini',
      messages,
      temperature: 0.3,
      max_tokens: 350
    });

    const content = response.choices[0]?.message?.content ?? '{}';
    const parsed = JSON.parse(content) as AiRawResponse;

    if (!parsed.direction || !parsed.summary || !parsed.advice) {
      throw new Error('AI response missing required fields');
    }

    return normalizeAiResult(parsed, options);
  } catch (error) {
    logger.error('AI case analysis failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return fallbackResponse(text);
  }
};

const buildMessages = (
  text: string,
  options: AiContextOptions
): ChatCompletionMessageParam[] => {
  const systemBlocks = [BASE_PROMPT];

  if (options.direction) {
    systemBlocks.push(`Потенциальное направление запроса: ${options.direction}.`);
  }

  if (options.kbArticles?.length) {
    systemBlocks.push(`Используй материалы: ${options.kbArticles.join(', ')}.`);
  }

  if (options.kbContext) {
    systemBlocks.push(`KB_CONTEXT:\n${options.kbContext}`);
  }

  if (options.externalContext) {
    systemBlocks.push(
      [
        'Используй приведённый ниже контекст с сайта SRVT строго как базу знаний.',
        'Не выдумывай дополнительные услуги и факты, которых нет в контексте.',
        'Отвечай в стилистике SRVT, опираясь на реальные формулировки и форматы работы компании.',
        '',
        'Если контекст содержит информацию, связанную с вопросом пользователя, — используй её в первую очередь.',
        'Если информации недостаточно, давай общий ответ, но не придумывай детали о SRVT.',
        '',
        'Приоритет источников:',
        '1) Контекст SRVT ниже;',
        '2) Логика диалога (предыдущие сообщения);',
        '3) Общие знания модели.',
        '',
        'КОНТЕКСТ SRVT:',
        options.externalContext
      ].join('\n')
    );
  }

  const systemContent = systemBlocks.join('\n\n');

  return [
    { role: 'system', content: systemContent },
    { role: 'user', content: text }
  ];
};

export const nextSolutionStep = async (
  dialog: SolutionDialogTurn[],
  kbContext: string | null,
  externalContext: string | null = null
): Promise<SolutionStepResult> => {
  if (!openaiClient) {
    return fallbackSolutionStep();
  }

  try {
    const messagesPayload = buildSolutionMessages(dialog, kbContext, externalContext);
    const response = await openaiClient.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: messagesPayload,
      temperature: 0.4,
      max_tokens: 400,
      response_format: { type: 'json_object' }
    });
    const content = response.choices[0]?.message?.content ?? '';
    const parsed = safeParseSolutionResponse(content);
    if (!parsed || typeof parsed.botMessage !== 'string') {
      return fallbackSolutionStep(
        'AI не вернул структурированный ответ. Эксперт СРВТ, пожалуйста, свяжитесь и уточните детали.'
      );
    }
    const botMessage = parsed.botMessage;
    return {
      direction: isDirection(parsed.direction) ? parsed.direction : 'other',
      botMessage,
      managerSummary: parsed.managerSummary,
      aiReady: Boolean(parsed.aiReady)
    };
  } catch (error) {
    logger.error('AI solution step failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return fallbackSolutionStep();
  }
};

export const nextSubsidyClassificationStep = async (
  dialog: SolutionDialogTurn[],
  previous?: SubsidyClassification
): Promise<SubsidyClassificationStepResult> => {
  const baseClassification = previous ?? EMPTY_SUBSIDY_CLASSIFICATION;

  if (!openaiClient) {
    return fallbackSubsidyClassificationStep(baseClassification);
  }

  try {
    const messagesPayload = buildSubsidyMessages(dialog, baseClassification);
    const response = await openaiClient.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: messagesPayload,
      temperature: 0.3,
      max_tokens: 700,
      response_format: { type: 'json_object' }
    });

    const content = response.choices[0]?.message?.content ?? '';
    const parsed: Record<string, unknown> = safeParseSubsidyJson(content) ?? {};

    const fieldsPayload =
      (parsed.fields as Record<string, unknown> | undefined) ?? {};
    const update = prepareClassificationUpdate(fieldsPayload);
    const classification = mergeClassification(baseClassification, update);

    const needMore =
      typeof parsed.needMore === 'boolean'
        ? parsed.needMore
        : !hasEssentialFields(classification);

    let followUpQuestion =
      typeof parsed.followUpQuestion === 'string' && parsed.followUpQuestion.trim().length
        ? parsed.followUpQuestion.trim()
        : undefined;
    if (!followUpQuestion || followUpQuestion.length < 8) {
      followUpQuestion = buildFollowUpQuestion(classification);
    }

    const rawBotMessage =
      typeof parsed.botMessage === 'string' ? parsed.botMessage : undefined;
    const botMessage =
      sanitizeBotMessage(rawBotMessage) ??
      buildSalesBotMessage(classification, followUpQuestion);

    return {
      classification,
      botMessage,
      needMore,
      followUpQuestion
    };
  } catch (error) {
    logger.error('AI subsidy classification failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return fallbackSubsidyClassificationStep(baseClassification);
  }
};

export const nextServiceConsultationStep = async (
  category: ServiceCategory,
  dialog: SolutionDialogTurn[],
  externalContext: string | null = null
): Promise<ServiceConsultationStepResult> => {
  const playbook = SERVICE_PLAYBOOK[category];
  if (!playbook) {
    return {
      botMessage: messages.fallback,
      needMore: false
    };
  }
  if (!openaiClient) {
    return fallbackServiceStep(playbook);
  }
  try {
    const contextBlocks = [
      SERVICE_CONSULT_PROMPT,
      `Категория: ${playbook.label}.`,
      playbook.aiPrompt
    ].filter(Boolean);
    if (externalContext) {
      contextBlocks.push(`SRVT_WEB_CONTEXT:\n${externalContext}`);
    }
    const prompt = contextBlocks.join('\n\n');

    const messagesPayload = buildServiceMessages(dialog, prompt);
    const response = await openaiClient.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: messagesPayload,
      temperature: 0.35,
      max_tokens: 350,
      response_format: { type: 'json_object' }
    });
    const content = response.choices[0]?.message?.content ?? '';
    const parsed = safeParseServiceResponse(content);
    if (!parsed || typeof parsed.botMessage !== 'string') {
      return fallbackServiceStep(playbook);
    }
    return {
      botMessage: sanitizeBotMessage(parsed.botMessage) ?? playbook.defaultFollowUp,
      needMore: typeof parsed.needMore === 'boolean' ? parsed.needMore : false
    };
  } catch (error) {
    logger.error('ai_service_consult_fail', {
      category,
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return fallbackServiceStep(playbook);
  }
};

const buildSolutionMessages = (
  dialog: SolutionDialogTurn[],
  kbContext: string | null,
  externalContext: string | null
): ChatCompletionMessageParam[] => {
  const systemBlocks = [SOLUTION_PROMPT];
  if (kbContext) {
    systemBlocks.push(`KB_CONTEXT:\n${kbContext}`);
  }
  if (externalContext) {
    systemBlocks.push(
      [
        'Используй приведённый ниже контекст с сайта SRVT строго как базу знаний.',
        'Не выдумывай дополнительные услуги и факты, которых нет в контексте.',
        'Отвечай в стилистике SRVT, опираясь на реальные формулировки и форматы работы компании.',
        '',
        'Если контекст содержит информацию, связанную с вопросом пользователя, — используй её в первую очередь.',
        'Если информации недостаточно, давай общий ответ, но не придумывай детали о SRVT.',
        '',
        'Приоритет источников:',
        '1) Контекст SRVT ниже;',
        '2) Логика диалога (предыдущие сообщения);',
        '3) Общие знания модели.',
        '',
        'КОНТЕКСТ SRVT:',
        externalContext
      ].join('\n')
    );
  }

  const base: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemBlocks.join('\n\n') }
  ];

  const turns = dialog.length ? dialog : [{ role: 'user', text: 'Опишите вашу задачу.' }];

  const dialogMessages = turns.map<ChatCompletionMessageParam>((turn) => ({
    role: turn.role === 'assistant' ? 'assistant' : 'user',
    content: turn.text
  }));

  return base.concat(dialogMessages);
};

interface ParsedSolutionPayload {
  direction?: string;
  botMessage?: string;
  managerSummary?: string;
  aiReady?: boolean;
}

const safeParseSolutionResponse = (
  raw: string
): ParsedSolutionPayload | null => {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as ParsedSolutionPayload;
  } catch {
    // try to extract substring between first { and last }
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start !== -1 && end !== -1 && end > start) {
      try {
        return JSON.parse(raw.slice(start, end + 1)) as ParsedSolutionPayload;
      } catch (error) {
        logger.error('solution_ai_raw', { error, raw });
        return null;
      }
    }
    logger.error('solution_ai_raw', { raw });
    return null;
  }
};

const buildSubsidyMessages = (
  dialog: SolutionDialogTurn[],
  previous: SubsidyClassification
): ChatCompletionMessageParam[] => {
  const systemBlocks = [SUBSIDY_PROMPT];
  if (previous) {
    systemBlocks.push(`PREVIOUS_FIELDS:\n${JSON.stringify(previous)}`);
  }

  const base: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemBlocks.join('\n\n') }
  ];

  const turns = dialog.length
    ? dialog
    : [{ role: 'user', text: 'Расскажите, чем занимаетесь и какие расходы хотите компенсировать.' }];

  const dialogMessages = turns.map<ChatCompletionMessageParam>((turn) => ({
    role: turn.role === 'assistant' ? 'assistant' : 'user',
    content: turn.text
  }));

  return base.concat(dialogMessages);
};

const safeParseSubsidyJson = (raw: string): Record<string, unknown> | null => {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start === -1 || end === -1 || end <= start) {
      logger.error('subsidy_ai_raw_unparsable', { raw });
      return null;
    }
    try {
      return JSON.parse(raw.slice(start, end + 1)) as Record<string, unknown>;
    } catch (error) {
      logger.error('subsidy_ai_raw_slice_parse', { error, raw });
      return null;
    }
  }
};

const fallbackServiceStep = (
  playbook: ServicePlaybookEntry
): ServiceConsultationStepResult => ({
  botMessage: playbook.defaultFollowUp,
  needMore: true
});

const buildServiceMessages = (
  dialog: SolutionDialogTurn[],
  prompt: string
): ChatCompletionMessageParam[] => {
  const base: ChatCompletionMessageParam[] = [{ role: 'system', content: prompt }];
  const turns = dialog.length
    ? dialog
    : [{ role: 'assistant', text: 'Расскажите, что хотите решить.' }];
  return base.concat(
    turns.map<ChatCompletionMessageParam>((turn) => ({
      role: turn.role === 'assistant' ? 'assistant' : 'user',
      content: turn.text
    }))
  );
};

const safeParseServiceResponse = (
  raw: string
): { botMessage?: string; needMore?: boolean } | null => {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as { botMessage?: string; needMore?: boolean };
  } catch {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start === -1 || end === -1 || end <= start) {
      logger.error('service_ai_raw_unparsable', { raw });
      return null;
    }
    try {
      return JSON.parse(raw.slice(start, end + 1)) as { botMessage?: string; needMore?: boolean };
    } catch (error) {
      logger.error('service_ai_raw_slice_parse', { error, raw });
      return null;
    }
  }
};

const normalizeStringArray = <T extends string>(value: unknown): T[] => {
  if (Array.isArray(value)) {
    return value
      .map((item) =>
        typeof item === 'string' ? (item.trim().toLowerCase() as T) : undefined
      )
      .filter((item): item is T => Boolean(item));
  }
  return [];
};

const normalizeRegionValue = (value: unknown): SubsidyRegion | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (['moscow', 'msk', 'москва'].includes(normalized)) {
    return 'moscow';
  }
  if (['spb', 'saint-petersburg', 'санкт-петербург', 'питер'].includes(normalized)) {
    return 'spb';
  }
  if (['dfo', 'far east', 'дфо', 'дальний восток'].includes(normalized)) {
    return 'dfo';
  }
  if (['fo', 'rf', 'россия', 'russia', 'ru'].includes(normalized)) {
    return 'fo';
  }
  if (['other'].includes(normalized)) {
    return 'other';
  }
  if (['unknown', ''].includes(normalized)) {
    return 'unknown';
  }
  return 'other';
};

const normalizeBudgetBoundary = (value: unknown): number | null | undefined => {
  if (value === null) {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.round(value));
  }
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[^\d.]/g, ''));
    if (Number.isFinite(parsed)) {
      return Math.max(0, Math.round(parsed));
    }
  }
  return undefined;
};

const normalizeExportValue = (value: unknown): boolean | null | undefined => {
  if (typeof value === 'boolean') {
    return value;
  }
  if (value === null) {
    return null;
  }
  return undefined;
};

const prepareClassificationUpdate = (
  fields: Record<string, unknown>
): Partial<SubsidyClassification> => {
  const sectors = normalizeStringArray<SubsidySector>(fields.sectors);
  const costTypes = normalizeStringArray<SubsidyCostType>(fields.costTypes);
  const excludeSectors = normalizeStringArray<SubsidySector>(fields.excludeSectors);

  const region = normalizeRegionValue(fields.region);
  const exportFlag = normalizeExportValue(fields.export);
  const budgetFrom = normalizeBudgetBoundary(fields.budgetFrom);
  const budgetTo = normalizeBudgetBoundary(fields.budgetTo);

  return {
    sectors: sectors.length ? sectors : undefined,
    costTypes: costTypes.length ? costTypes : undefined,
    excludeSectors: excludeSectors.length ? excludeSectors : undefined,
    region,
    export: exportFlag,
    budgetFrom,
    budgetTo,
    notes:
      typeof fields.notes === 'string' && fields.notes.trim()
        ? fields.notes.trim().slice(0, 400)
        : undefined
  };
};

const mergeClassification = (
  prev: SubsidyClassification,
  update: Partial<SubsidyClassification>
): SubsidyClassification => ({
  sectors: update.sectors && update.sectors.length ? update.sectors : prev.sectors,
  costTypes: update.costTypes && update.costTypes.length ? update.costTypes : prev.costTypes,
  region: update.region ?? prev.region,
  export:
    typeof update.export === 'boolean' || update.export === null ? update.export : prev.export,
  budgetFrom:
    typeof update.budgetFrom === 'number' || update.budgetFrom === null
      ? update.budgetFrom
      : prev.budgetFrom,
  budgetTo:
    typeof update.budgetTo === 'number' || update.budgetTo === null
      ? update.budgetTo
      : prev.budgetTo,
  notes: update.notes ?? prev.notes,
  excludeSectors:
    update.excludeSectors && update.excludeSectors.length
      ? update.excludeSectors
      : prev.excludeSectors
});

const hasEssentialFields = (classification: SubsidyClassification): boolean => {
  const hasSector = classification.sectors.length > 0;
  const hasRegion = classification.region !== 'unknown';
  const hasBudget =
    (typeof classification.budgetFrom === 'number' && classification.budgetFrom > 0) ||
    (typeof classification.budgetTo === 'number' && classification.budgetTo > 0);
  return hasSector && hasRegion && hasBudget;
};

type MissingField = 'region' | 'budget' | 'sector' | 'cost' | 'export' | null;

const resolveMissingField = (classification: SubsidyClassification): MissingField => {
  if (classification.region === 'unknown') {
    return 'region';
  }
  const hasBudget =
    (typeof classification.budgetFrom === 'number' && classification.budgetFrom > 0) ||
    (typeof classification.budgetTo === 'number' && classification.budgetTo > 0);
  if (!hasBudget) {
    return 'budget';
  }
  if (!classification.sectors.length) {
    return 'sector';
  }
  if (!classification.costTypes.length) {
    return 'cost';
  }
  if (typeof classification.export !== 'boolean') {
    return 'export';
  }
  return null;
};

const sectorHookLabels: Partial<Record<SubsidySector, string>> = {
  it: 'По ИТ-проектам доступны возвраты до 30% затрат.',
  logistics: 'Логистика получает компенсации на маршруты и склады.',
  tourism: 'Для туристических проектов есть гранты на продвижение.',
  agrotourism: 'Агротуризм субсидируют на развитие маршрутов и инфраструктуры.',
  agro: 'АПК поддерживают грантами на технику, корма и маркетинг.',
  export: 'Экспортёрам компенсируют логистику и сертификацию.',
  services: 'Сервисные компании могут закрыть часть расходов через субсидии.',
  manufacturing: 'Производителям компенсируют оборудование и R&D.',
  construction: 'Стройке помогают с финансированием инфраструктуры.',
  education: 'Образовательные проекты поддерживают грантами на контент и продвижение.',
  healthcare: 'Медпроекты получают льготные компенсации на оборудование.',
  other: 'По вашему направлению тоже есть программы возврата затрат.'
};

const describeSectorHook = (classification: SubsidyClassification): string | null => {
  if (!classification.sectors.length) {
    return null;
  }
  const primary = classification.sectors[0];
  return sectorHookLabels[primary] ?? null;
};

const describeRegionHook = (classification: SubsidyClassification): string | null => {
  switch (classification.region) {
    case 'moscow':
      return 'В Москве действует несколько быстрых программ возврата затрат.';
    case 'spb':
      return 'Петербург также компенсирует расходы бизнеса.';
    case 'dfo':
      return 'Для Дальнего Востока сейчас расширенные лимиты поддержки.';
    case 'fo':
      return 'По федеральным программам можно заявиться из любого региона РФ.';
    case 'other':
      return 'Региональные фонды тоже подключаются к таким кейсам.';
    default:
      return null;
  }
};

const buildFollowUpQuestion = (classification: SubsidyClassification): string => {
  const missing = resolveMissingField(classification);
  const sectorHook = describeSectorHook(classification);

  switch (missing) {
    case 'region':
      return sectorHook
        ? `${sectorHook} Уточните, где зарегистрирована компания — Москва, Петербург или другой регион?`
        : 'Уточните, где зарегистрирована компания — Москва, Петербург или другой регион?';
    case 'budget':
      return sectorHook
        ? `${sectorHook} Чтобы прикинуть компенсацию, обозначьте диапазон расходов: до 1 млн, 1–5 млн или больше?`
        : 'Чтобы прикинуть компенсацию, обозначьте диапазон расходов: до 1 млн, 1–5 млн или больше?';
    case 'sector':
      return 'Расскажите коротко, в какой сфере работает бизнес. Так смогу подсказать конкретные программы.';
    case 'cost':
      return 'Какие расходы хотели бы компенсировать — оборудование, логистика, маркетинг или что-то ещё?';
    case 'export':
      return 'Есть ли экспорт или зарубежные продажи? Для таких кейсов доступен отдельный пул мер.';
    default:
      return messages.subsidyNeedFieldsHint;
  }
};

const buildSalesBotMessage = (
  classification: SubsidyClassification,
  followUpQuestion?: string
): string => {
  const sectorHook = describeSectorHook(classification);
  const regionHook = describeRegionHook(classification);
  const hookText = [sectorHook, regionHook]
    .filter(Boolean)
    .join(' ')
    .trim();

  const intro = hookText.length
    ? hookText
    : 'По вашему направлению действительно есть программы компенсаций.';

  const question = followUpQuestion ?? messages.subsidyNeedFieldsHint;
  const closing =
    'Соберём этот нюанс и передадим расчёт эксперту СРВТ, чтобы не оставить деньги в бюджете.';

  return `${intro} ${question} ${closing}`.replace(/\s+/g, ' ').trim();
};

const sanitizeBotMessage = (message?: string | null): string | null => {
  const trimmed = message?.replace(/\s+/g, ' ').trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.length <= 420) {
    return trimmed;
  }
  const cut = trimmed.lastIndexOf(' ', 420);
  return (cut === -1 ? trimmed.slice(0, 420) : trimmed.slice(0, cut)).trim();
};

const sanitizeFollowUpQuestion = (question?: string | null): string | null => {
  const trimmed = question?.trim();
  if (!trimmed || trimmed.length < 4) {
    return null;
  }
  if (trimmed.length <= 220) {
    return trimmed;
  }
  const cut = trimmed.lastIndexOf(' ', 220);
  return (cut === -1 ? trimmed.slice(0, 220) : trimmed.slice(0, cut)).trim();
};

const clampConfidence = (value?: number): number => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
};

const normalizeAiResult = (
  raw: AiRawResponse,
  options: AiContextOptions
): AiCaseResult => {
  const direction = isDirection(raw.direction) ? raw.direction : 'other';
  const riskLevel = normalizeLevel(raw.risk_level);
  const potentialValue = normalizeLevel(raw.potential_value);
  const kbUsed =
    typeof raw.kb_used === 'boolean'
      ? raw.kb_used
      : Boolean(options.kbContext || options.kbArticles?.length);
  const articles =
    Array.isArray(raw.articles) && raw.articles.length
      ? raw.articles
      : options.kbArticles;

  return {
    direction,
    summary: raw.summary ?? '',
    advice: raw.advice ?? '',
    riskLevel,
    potentialValue,
    kbUsed,
    articles
  };
};

const normalizeLevel = (value?: string): 'low' | 'medium' | 'high' | undefined => {
  if (!value) {
    return undefined;
  }
  const normalized = value.toLowerCase();
  if (normalized === 'low' || normalized === 'medium' || normalized === 'high') {
    return normalized;
  }
  return undefined;
};

const isDirection = (value?: string): value is AiDirection => {
  if (!value) {
    return false;
  }
  return ['finance', 'logistics', 'payments', 'analytics', 'other'].includes(value);
};

export async function buildAiContextFromSupabase(
  userText: string
): Promise<Pick<AiContextOptions, 'externalContext' | 'externalSources'>> {
  const query = userText?.trim();
  if (!query) {
    return { externalContext: null, externalSources: [] };
  }

  const results = await searchSrvtRag(query, { matchCount: 5, minSimilarity: 0.6 });
  const top = results.slice(0, 8);
  if (!top.length) {
    return { externalContext: null, externalSources: [] };
  }

  const externalContext = top
    .map((item) => {
      const url = item.url ?? 'не указан';
      return `[Источник: ${url}]\n${item.content}`;
    })
    .join('\n\n');

  const externalSources = Array.from(
    new Set(top.map((item) => item.url).filter((url): url is string => Boolean(url)))
  );

  return { externalContext, externalSources };
}


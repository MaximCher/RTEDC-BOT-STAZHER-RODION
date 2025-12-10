import { Markup, Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { messages, formatSubsidyEstimationForUser } from '../messages';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { resetFlow, SubsidySolutionState, SubsidyStepSnapshot } from '../../types/session';
import { nextSubsidyClassificationStep } from '../../services/aiAssistant';
import { calculateSubsidyResult } from '../../services/subsidyCalculator';
import { logger } from '../../utils/logger';
import type {
  SubsidyClassification,
  SubsidyCostType,
  SubsidyRegion,
  SubsidySector
} from '../../types/subsidy';
import { splitToTelegramChunks } from '../../utils/text';
import { mainMenuKeyboard } from '../keyboards/mainMenu';
import { detectCompanySectorFromText } from '../../services/subsidies/companyProfile';
import type { CompanySector } from '../../services/subsidies/companyProfile';

export const registerSubsidyHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:subsidy:start:ai',
    withCallbackGuard(async (ctx) => {
      resetFlow(ctx.session, 'subsidy_solution');
      ctx.session.subsidy = {
        dialog: [],
        turnCount: 0,
        aiReady: false,
        needMore: true,
        clarifyCount: 0,
        classification: createEmptySubsidyClassification(),
        history: []
      };
      await ctx.reply(messages.subsidyIntroText, subsidyDialogKeyboard());
    })
  );

  bot.action(
    'srvt:subsidy:wait:noop',
    withCallbackGuard(async (ctx) => {
      await ctx.answerCbQuery(messages.subsidyAiHoldHint, { show_alert: false });
    })
  );

  bot.action(
    'srvt:subsidy:step:back',
    withCallbackGuard(async (ctx) => {
      await ctx.answerCbQuery(messages.subsidyBackOk, { show_alert: false });
      resetFlow(ctx.session);
      await ctx.reply(messages.flowBackToMenu, mainMenuKeyboard());
    })
  );
};

export const handleSubsidySolutionText = async (ctx: CustomContext): Promise<boolean> => {
  if (ctx.session.flow !== 'subsidy_solution') {
    return false;
  }

  const text = extractMessageText(ctx);
  if (!text) {
    return false;
  }

  const state = ensureState(ctx);
  const cleanText = sanitizeUserMessage(text);
  maybeRestartConversation(state, cleanText);
  state.dialog.push({ role: 'user', text: cleanText, ts: new Date().toISOString() });
  state.turnCount = (state.turnCount ?? 0) + 1;
  snapshotState(state);

  try {
    const aiStep = await nextSubsidyClassificationStep(state.dialog, state.classification);
    state.classification = applyTextHeuristics(aiStep.classification, cleanText);
    state.needMore = aiStep.needMore;
    const hasBasics = hasEssentialClassification(state.classification);
    state.aiReady = !aiStep.needMore && hasBasics;

    const stillNeedDetails = aiStep.needMore || !hasBasics;
    let assistantReply = aiStep.botMessage || messages.subsidyNeedFieldsHint;

    const readyDespiteNeed =
      hasBasics &&
      (((state.clarifyCount ?? 0) >= 1) || ((state.turnCount ?? 0) >= 1));

    if (stillNeedDetails && !readyDespiteNeed) {
      state.clarifyCount = (state.clarifyCount ?? 0) + 1;

      if ((state.clarifyCount ?? 0) >= 3) {
        assistantReply = [
          assistantReply,
          '',
          messages.subsidyManualEstimateSoft
        ]
          .filter(Boolean)
          .join('\n');
      }

      state.dialog.push({ role: 'assistant', text: assistantReply, ts: new Date().toISOString() });
      ctx.session.subsidy = state;
      await sendChunkedReplies(ctx, assistantReply, subsidyDialogKeyboard());
      return true;
    }

    state.clarifyCount = 0;

    const estimation = await calculateSubsidyResult(state.classification);
    state.programs = estimation.programs;
    state.hasAmountEstimate = estimation.hasAmountEstimate;

    if (!estimation.programs.length && aiStep.needMore) {
      state.needMore = true;
      state.clarifyCount = (state.clarifyCount ?? 0) + 1;
      let followUpReply = assistantReply;
      if ((state.clarifyCount ?? 0) >= 3) {
        followUpReply = [assistantReply, '', messages.subsidyManualEstimateSoft].filter(Boolean).join('\n');
      }
      state.dialog.push({ role: 'assistant', text: followUpReply, ts: new Date().toISOString() });
      ctx.session.subsidy = state;
      await sendChunkedReplies(ctx, followUpReply, subsidyDialogKeyboard());
      return true;
    }

    const estimationText =
      estimation.programs.length > 0
        ? formatSubsidyEstimationForUser(
            estimation.programs,
            state.classification,
            estimation.hasAmountEstimate
          )
        : messages.subsidyManualEstimate;

    const finalText = estimationText;

    state.dialog.push({ role: 'assistant', text: finalText, ts: new Date().toISOString() });
    ctx.session.subsidy = state;
    await sendChunkedReplies(ctx, finalText, subsidyDialogKeyboard());
    return true;
  } catch (error) {
    logger.error('subsidy_solution_step_failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    await ctx.reply(messages.subsidyAiFallback, subsidyDialogKeyboard());
    return true;
  }
};

const subsidyDialogKeyboard = () =>
  Markup.inlineKeyboard([
    [
      Markup.button.callback('⏳ Просто подожду ответ', 'srvt:subsidy:wait:noop'),
      Markup.button.callback('📩 Отправить данные эксперту', 'srvt:lead:start:subsidy_application')
    ],
    [Markup.button.callback('↩ В главное меню', 'srvt:menu:open:root')]
  ]);

const ensureState = (ctx: CustomContext): SubsidySolutionState => {
  if (!ctx.session.subsidy) {
    ctx.session.subsidy = {
      dialog: [],
      aiReady: false,
      needMore: true,
      clarifyCount: 0,
      turnCount: 0,
      classification: createEmptySubsidyClassification(),
      history: []
    };
  }
  if (!ctx.session.subsidy.classification) {
    ctx.session.subsidy.classification = createEmptySubsidyClassification();
  }
  if (!ctx.session.subsidy.history) {
    ctx.session.subsidy.history = [];
  }
  if (typeof ctx.session.subsidy.clarifyCount !== 'number') {
    ctx.session.subsidy.clarifyCount = 0;
  }
  return ctx.session.subsidy;
};

const extractMessageText = (ctx: CustomContext): string | undefined => {
  const message = ctx.message;
  if (message && 'text' in message) {
    const payload = message as { text?: string };
    return payload.text?.trim();
  }
  return undefined;
};

const hasEssentialClassification = (
  classification?: SubsidySolutionState['classification']
): boolean => {
  if (!classification) {
    return false;
  }
  const hasSector = classification.sectors?.length > 0;
  const hasRegion = classification.region && classification.region !== 'unknown';
  const hasBudget =
    (typeof classification.budgetFrom === 'number' && classification.budgetFrom > 0) ||
    (typeof classification.budgetTo === 'number' && classification.budgetTo > 0);
  return Boolean(hasSector && hasRegion && hasBudget);
};

const NOISE_WORDS = ['луна', 'космос', 'мама сказала', 'море', 'марс', 'галактика', 'орбита'];

const sanitizeUserMessage = (text: string): string => {
  let cleaned = text;
  NOISE_WORDS.forEach((word) => {
    const regex = new RegExp(word, 'gi');
    cleaned = cleaned.replace(regex, ' ');
  });
  cleaned = replaceBudgetSlang(cleaned);
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  return cleaned.length ? cleaned : text.trim();
};

const replaceBudgetSlang = (text: string): string =>
  text.replace(/(\d+(?:[.,]\d+)?)\s*(кк|kk)/gi, (_, num) => {
    const parsed = Number(num.replace(',', '.'));
    if (!Number.isFinite(parsed)) {
      return _;
    }
    return String(Math.round(parsed * 1_000_000));
  });

const maybeRestartConversation = (state: SubsidySolutionState, text: string): void => {
  if (!shouldRestartSubsidyConversation(state, text)) {
    return;
  }
  state.dialog = [];
  state.classification = createEmptySubsidyClassification();
  state.programs = undefined;
  state.hasAmountEstimate = undefined;
  state.aiReady = false;
  state.needMore = true;
  state.clarifyCount = 0;
  state.turnCount = 0;
  state.history = [];
};

const shouldRestartSubsidyConversation = (
  state: SubsidySolutionState,
  text: string
): boolean => {
  if (!state.aiReady && !state.programs?.length) {
    return false;
  }
  const normalized = text.toLowerCase();
  const shortQuery = normalized.split(/\s+/).filter(Boolean).length <= 6;
  const patterns = [/^а?\s*по\b/, /\bнов(ый|ая|ое)\b/, /\bдруг(ой|ая|ое)\b/, /\bснова\b/, /\bещё\b/];
  if (patterns.some((regex) => regex.test(normalized)) && shortQuery) {
    return true;
  }
  return normalized.includes('начнём') || normalized.includes('заново');
};

const createEmptySubsidyClassification = (): SubsidyClassification => ({
  sectors: [],
  costTypes: [],
  region: 'unknown',
  export: null,
  budgetFrom: null,
  budgetTo: null
});

const snapshotState = (state: SubsidySolutionState): void => {
  if (!state.history) {
    state.history = [];
  }
  const classificationClone = JSON.parse(
    JSON.stringify(state.classification ?? createEmptySubsidyClassification())
  ) as SubsidyClassification;
  const snapshot: SubsidyStepSnapshot = {
    classification: classificationClone,
    dialogLength: state.dialog.length,
    clarifyCount: state.clarifyCount ?? 0
  };
  state.history.push(snapshot);
};

const sendChunkedReplies = async (
  ctx: CustomContext,
  text: string,
  keyboard: ReturnType<typeof subsidyDialogKeyboard>
): Promise<void> => {
  const chunks = splitToTelegramChunks(text);
  for (let i = 0; i < chunks.length; i += 1) {
    const chunkKeyboard = i === chunks.length - 1 ? keyboard : undefined;
    await ctx.reply(chunks[i], chunkKeyboard);
  }
};

const mapCompanySectorToSubsidySector = (sector: CompanySector): SubsidySector => {
  switch (sector) {
    case 'it':
      return 'it';
    case 'logistics':
      return 'logistics';
    case 'agro':
      return 'agro';
    case 'tourism':
      return 'tourism';
    case 'industry':
      return 'manufacturing';
    case 'finance':
      return 'services';
    default:
      return 'other';
  }
};

const applyTextHeuristics = (
  classification: SubsidyClassification,
  text: string
): SubsidyClassification => {
  const hints = inferClassificationHints(text);
  const detectedSector = detectCompanySectorFromText(text);
  if (!hints) {
    if (!classification.sectors.length && detectedSector) {
      return {
        ...classification,
        sectors: [mapCompanySectorToSubsidySector(detectedSector)]
      };
    }
    return classification;
  }

  let changed = false;
  const next: SubsidyClassification = { ...classification };

  if (!classification.sectors.length && hints.sectors?.length) {
    next.sectors = hints.sectors;
    changed = true;
  }
  if (!classification.costTypes.length && hints.costTypes?.length) {
    next.costTypes = hints.costTypes;
    changed = true;
  }
  if (classification.region === 'unknown' && hints.region) {
    next.region = hints.region;
    changed = true;
  }
  if (typeof classification.export !== 'boolean' && typeof hints.export === 'boolean') {
    next.export = hints.export;
    changed = true;
  }
  const hasBudgetFrom =
    typeof classification.budgetFrom === 'number' && classification.budgetFrom > 0;
  const hasBudgetTo = typeof classification.budgetTo === 'number' && classification.budgetTo > 0;
  if (!hasBudgetFrom && typeof hints.budgetFrom === 'number') {
    next.budgetFrom = hints.budgetFrom;
    changed = true;
  }
  if (!hasBudgetTo && typeof hints.budgetTo === 'number') {
    next.budgetTo = hints.budgetTo;
    changed = true;
  }

  if (!next.sectors.length && detectedSector) {
    next.sectors = [mapCompanySectorToSubsidySector(detectedSector)];
    changed = true;
  }

  return changed ? next : classification;
};

interface ClassificationHints {
  sectors?: SubsidySector[];
  costTypes?: SubsidyCostType[];
  region?: SubsidyRegion;
  export?: boolean;
  budgetFrom?: number;
  budgetTo?: number;
}

const inferClassificationHints = (text: string): ClassificationHints | null => {
  if (!text || text.trim().length < 2) {
    return null;
  }

  const hints: ClassificationHints = {};
  const sectors = detectSectors(text);
  if (sectors.length) {
    hints.sectors = sectors;
  }
  const costTypes = detectCostTypes(text);
  if (costTypes.length) {
    hints.costTypes = costTypes;
  }
  const region = detectRegion(text);
  if (region) {
    hints.region = region;
  }
  const exportFlag = detectExportIntent(text);
  if (typeof exportFlag === 'boolean') {
    hints.export = exportFlag;
  }
  const budgetHints = detectBudget(text);
  if (budgetHints) {
    hints.budgetFrom = budgetHints.budgetFrom ?? undefined;
    hints.budgetTo = budgetHints.budgetTo ?? undefined;
  }

  return Object.keys(hints).length ? hints : null;
};

const detectSectors = (text: string): SubsidySector[] => {
  const found = new Set<SubsidySector>();
  for (const hint of SECTOR_HINTS) {
    if (hint.patterns.some((pattern) => pattern.test(text))) {
      found.add(hint.sector);
    }
  }
  return Array.from(found);
};

const detectCostTypes = (text: string): SubsidyCostType[] => {
  const found = new Set<SubsidyCostType>();
  for (const hint of COST_TYPE_HINTS) {
    if (hint.patterns.some((pattern) => pattern.test(text))) {
      found.add(hint.costType);
    }
  }
  return Array.from(found);
};

const detectRegion = (text: string): SubsidyRegion | null => {
  for (const hint of REGION_HINTS) {
    if (hint.patterns.some((pattern) => pattern.test(text))) {
      return hint.region;
    }
  }
  return null;
};

const detectExportIntent = (text: string): boolean | null => {
  if (EXPORT_FALSE_PATTERNS.some((pattern) => pattern.test(text))) {
    return false;
  }
  if (EXPORT_TRUE_PATTERNS.some((pattern) => pattern.test(text))) {
    return true;
  }
  return null;
};

const detectBudget = (
  text: string
): { budgetFrom?: number; budgetTo?: number } | null => {
  const matches = Array.from(text.matchAll(BUDGET_REGEX));
  if (!matches.length) {
    return null;
  }
  const values = matches
    .map((match) => parseBudgetValue(match[1], match[2]))
    .filter((value): value is number => typeof value === 'number' && value > 0);
  if (!values.length) {
    return null;
  }
  values.sort((a, b) => a - b);
  if (values.length === 1) {
    const value = values[0];
    return { budgetFrom: value, budgetTo: value };
  }
  return {
    budgetFrom: values[0],
    budgetTo: values[values.length - 1]
  };
};

const parseBudgetValue = (rawValue: string, rawUnit?: string): number | null => {
  if (!rawValue) {
    return null;
  }
  const normalizedNumber = rawValue.replace(/\s+/g, '').replace(',', '.');
  const base = Number(normalizedNumber);
  if (!Number.isFinite(base)) {
    return null;
  }
  const unit = rawUnit?.toLowerCase() ?? '';

  let multiplier = 1;
  if (unit.includes('млрд') || unit.includes('b')) {
    multiplier = 1_000_000_000;
  } else if (
    unit.includes('млн') ||
    unit.includes('миллион') ||
    unit === 'm' ||
    unit === 'kk' ||
    unit === 'кк'
  ) {
    multiplier = 1_000_000;
  } else if (
    unit.includes('тыс') ||
    unit === 'k' ||
    unit === 'к'
  ) {
    multiplier = 1_000;
  } else if (!unit && base < 100_000) {
    return null;
  }

  const value = Math.round(base * multiplier);
  return value > 0 ? value : null;
};

const SECTOR_HINTS: Array<{ sector: SubsidySector; patterns: RegExp[] }> = [
  {
    sector: 'it',
    patterns: [
      /\bit\b/i,
      /\bait\b/i,
      /\байти\b/i,
      /digital/i,
      /цифров/i,
      /маркетплейс/i,
      /marketplace/i,
      /разработ/i,
      /sdk/i,
      /saas/i
    ]
  },
  {
    sector: 'logistics',
    patterns: [/логист/i, /достав/i, /транспорт/i, /склад/i, /экспедиц/i, /растамож/i]
  },
  {
    sector: 'tourism',
    patterns: [/туризм/i, /travel/i, /гостини/i, /hotel/i, /маршрут/i]
  },
  {
    sector: 'agrotourism',
    patterns: [/агротур/i, /сельск.*туризм/i]
  },
  {
    sector: 'agro',
    patterns: [/агро/i, /сельхоз/i, /ферм/i, /аграр/i]
  },
  {
    sector: 'manufacturing',
    patterns: [/производ/i, /завод/i, /фабрик/i, /цех/i]
  },
  {
    sector: 'services',
    patterns: [/сервис/i, /услуг/i, /консалт/i, /service/i]
  },
  {
    sector: 'construction',
    patterns: [/строит/i, /инфраструкт/i, /девелоп/i]
  },
  {
    sector: 'education',
    patterns: [/образоват/i, /edtech/i, /обучен/i, /школ/i, /курс/i]
  },
  {
    sector: 'healthcare',
    patterns: [/медиц/i, /health/i, /clinic/i, /pharma/i, /healthcare/i]
  },
  {
    sector: 'export',
    patterns: [/экспорт/i, /зарубеж/i, /международ/i, /foreign/i]
  }
];

const COST_TYPE_HINTS: Array<{ costType: SubsidyCostType; patterns: RegExp[] }> = [
  {
    costType: 'equipment',
    patterns: [/оборуд/i, /станк/i, /техник/i, /машин/i]
  },
  {
    costType: 'logistics',
    patterns: [/логист/i, /достав/i, /транспорт/i, /склад/i, /растамож/i]
  },
  {
    costType: 'marketing',
    patterns: [/маркет/i, /реклам/i, /продвиж/i, /бренд/i]
  },
  {
    costType: 'certification',
    patterns: [/сертиф/i, /лиценз/i, /аккред/i]
  },
  {
    costType: 'payroll',
    patterns: [/зарп/i, /фот/i, /персонал/i, /штат/i, /команд/i]
  },
  {
    costType: 'r_and_d',
    patterns: [/r[&/]d/i, /исслед/i, /разработ/i, /прототип/i]
  },
  {
    costType: 'software',
    patterns: [/програм/i, /\bпо\b/i, /software/i, /лиценз/i, /saas/i]
  },
  {
    costType: 'training',
    patterns: [/обуч/i, /тренинг/i, /повыш.*квал/i, /education/i]
  },
  {
    costType: 'exhibitions',
    patterns: [/выстав/i, /экспо/i, /форум/i]
  }
];

const REGION_HINTS: Array<{ region: SubsidyRegion; patterns: RegExp[] }> = [
  {
    region: 'moscow',
    patterns: [/москв/i, /\bmsk\b/i]
  },
  {
    region: 'spb',
    patterns: [/питер/i, /санкт[-\s]?петербург/i, /\bspb\b/i]
  },
  {
    region: 'dfo',
    patterns: [/дфо/i, /дальн(ий)? восток/i, /владивосток/i, /камчат/i, /сахалин/i]
  },
  {
    region: 'fo',
    patterns: [/росси/i, /\brf\b/i, /по всей стране/i, /федерал/i]
  }
];

const EXPORT_TRUE_PATTERNS = [
  /экспорт/i,
  /зарубеж/i,
  /международ/i,
  /foreign/i,
  /cross[-\s]?border/i,
  /поставк.*за границу/i
];

const EXPORT_FALSE_PATTERNS = [/без экспорта/i, /только по росс/i, /без зарубеж/i];

const BUDGET_REGEX = /(\d[\d\s.,]*)\s*(млрд|миллиард|млн|миллион|тыс|тысяч|kk|кк|k|к|m|b)?/gi;


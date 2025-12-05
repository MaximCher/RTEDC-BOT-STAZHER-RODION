import { Markup, Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { messages, formatSubsidyEstimationForUser } from '../messages';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { resetFlow, SubsidySolutionState, SubsidyStepSnapshot } from '../../types/session';
import { nextSubsidyClassificationStep } from '../../services/aiAssistant';
import { calculateSubsidyResult } from '../../services/subsidyCalculator';
import { logger } from '../../utils/logger';
import type { SubsidyClassification } from '../../types/subsidy';
import { splitToTelegramChunks } from '../../utils/text';

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
      if (ctx.session.flow !== 'subsidy_solution') {
        await ctx.answerCbQuery(messages.subsidyBackUnavailable, { show_alert: false });
        return;
      }

      const state = ensureState(ctx);
      if (!state.history.length) {
        await ctx.answerCbQuery(messages.subsidyBackUnavailable, { show_alert: false });
        return;
      }

      const snapshot = state.history.pop();
      if (!snapshot) {
        await ctx.answerCbQuery(messages.subsidyBackUnavailable, { show_alert: false });
        return;
      }

      state.classification = snapshot.classification;
      state.dialog = state.dialog.slice(0, snapshot.dialogLength);
      state.clarifyCount = snapshot.clarifyCount;
      state.aiReady = false;
      state.needMore = true;
      ctx.session.subsidy = state;

      await ctx.answerCbQuery(messages.subsidyBackOk, { show_alert: false });
      await ctx.reply(messages.subsidyBackPrompt, subsidyDialogKeyboard());
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
    state.classification = aiStep.classification;
    state.needMore = aiStep.needMore;
    const hasBasics = hasEssentialClassification(state.classification);
    state.aiReady = !aiStep.needMore && hasBasics;

    const stillNeedDetails = aiStep.needMore || !hasBasics;
    let assistantReply = aiStep.botMessage || messages.subsidyNeedFieldsHint;

    const readyDespiteNeed =
      hasBasics &&
      (((state.clarifyCount ?? 0) >= 1) || ((state.turnCount ?? 0) >= 2));

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

    const introLine = stillNeedDetails && readyDespiteNeed ? messages.subsidyApproxEstimateIntro : assistantReply;
    const finalText = [introLine, '', estimationText].filter(Boolean).join('\n');

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
    [Markup.button.callback('↩️ Вернуться назад', 'srvt:subsidy:step:back')]
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


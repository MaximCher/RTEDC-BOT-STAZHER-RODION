import { Prisma } from '@prisma/client';
import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction } from '../../types/lead';
import { messages } from '../messages';
import { prisma } from '../../services/db';
import { logger } from '../../utils/logger';
import { withCallbackGuard } from '../../utils/callbackGuard';
import {
  KnowledgeDirection,
  getRelevantKnowledge
} from '../../services/knowledgeBase';
import { nextSolutionStep, buildAiContextFromSupabase } from '../../services/aiAssistant';
import { resetFlow, SolutionState } from '../../types/session';
import { solutionStepKeyboard } from '../keyboards/solution';
import { splitToTelegramChunks } from '../../utils/text';

const directionToKnowledge: Record<Direction, KnowledgeDirection> = {
  finance: 'finance',
  logistics: 'logistics',
  payments: 'payments',
  analytics: 'analytics',
  other: 'export'
};

export const registerCaseHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:solution:start:free',
    withCallbackGuard(async (ctx) => {
      resetFlow(ctx.session, 'solution');
      ctx.session.solution = {
        dialog: [],
        turnCount: 0,
        aiReady: false
      };
      await ctx.reply(messages.solutionIntroText, solutionStepKeyboard(false));
    })
  );

  bot.action(
    'srvt:solution:wait:noop',
    withCallbackGuard(async (ctx) => {
      await ctx.answerCbQuery(messages.solutionAwaitHint, { show_alert: false });
    })
  );
};

export const handleSolutionText = async (ctx: CustomContext): Promise<boolean> => {
  if (ctx.session.flow !== 'solution') {
    return false;
  }

  const rawText = extractMessageText(ctx);
  if (!rawText) {
    return false;
  }

  if (isOffTopic(rawText)) {
    await sendChunkedReplies(
      ctx,
      `${messages.solutionOffTopicShort}\n\n${messages.solutionOffTopicAsk}`,
      solutionStepKeyboard(false)
    );
    return true;
  }

  const solution = ensureSolutionState(ctx);
  const timestamp = new Date().toISOString();
  solution.dialog.push({ role: 'user', text: rawText, ts: timestamp });
  solution.turnCount += 1;
  ctx.session.solution = solution;

  if (solution.aiReady) {
    const reminder = [messages.solutionAfterReady, '', messages.solutionWaitingInfo]
      .filter(Boolean)
      .join('\n');
    await sendChunkedReplies(ctx, reminder, solutionStepKeyboard(true));
    return true;
  }

  const knowledgeDirection = solution.direction
    ? directionToKnowledge[solution.direction]
    : undefined;
  const kbInput = aggregateUserDialog(solution) || rawText;
  const kbSelection = await getRelevantKnowledge(kbInput, knowledgeDirection);
  const supabaseContext = await buildAiContextFromSupabase(rawText);

  const stepResult = await nextSolutionStep(
    solution.dialog,
    kbSelection?.context ?? null,
    supabaseContext.externalContext ?? null
  );

  solution.dialog.push({
    role: 'assistant',
    text: stepResult.botMessage,
    ts: new Date().toISOString()
  });
  solution.direction = stepResult.direction;
  solution.aiReady = stepResult.aiReady;
  if (stepResult.managerSummary) {
    solution.managerSummary = stepResult.managerSummary;
  }
  ctx.session.solution = solution;
  ctx.session.lastCase = {
    text: rawText,
    direction: stepResult.direction,
    summary: stepResult.managerSummary ?? '',
    advice: stepResult.botMessage,
    sources: Array.from(
      new Set([...(kbSelection?.articles ?? []), ...(supabaseContext.externalSources ?? [])])
    ),
    kbUsed: Boolean(kbSelection?.context || supabaseContext.externalContext)
  };

  if (ctx.from?.id) {
    try {
      await prisma.caseLog.create({
        data: {
          userId: BigInt(ctx.from.id),
          text: rawText,
          direction: stepResult.direction,
          summary: stepResult.managerSummary,
          advice: stepResult.botMessage,
          raw: {
            dialog: solution.dialog,
            managerSummary: solution.managerSummary,
            aiReady: solution.aiReady,
            kbSources: kbSelection?.articles ?? []
          } as unknown as Prisma.InputJsonValue
        }
      });
    } catch (error) {
      logger.error('Failed to persist case log', { error });
    }
  }

  let replyText = stepResult.botMessage;
  if (stepResult.aiReady) {
    replyText = [replyText, '', messages.solutionTransferHint].filter(Boolean).join('\n');
  }

  await sendChunkedReplies(ctx, replyText, solutionStepKeyboard(stepResult.aiReady));
  return true;
};

const ensureSolutionState = (ctx: CustomContext): SolutionState => {
  if (!ctx.session.solution) {
    ctx.session.solution = { dialog: [], turnCount: 0, aiReady: false };
  }
  return ctx.session.solution;
};

const aggregateUserDialog = (solution: SolutionState): string =>
  solution.dialog
    .filter((turn) => turn.role === 'user')
    .map((turn) => turn.text)
    .join('\n');

const isOffTopic = (text: string): boolean => {
  const trimmed = text.toLowerCase().trim();
  if (trimmed.length < 5) {
    return true;
  }
  const smallTalk = ['как дела', 'что делаешь', 'привет', 'hi', 'hello'];
  if (smallTalk.some((p) => trimmed.includes(p))) {
    return true;
  }
  const nonsense = ['на луну', 'котик', 'мем', 'шутка'];
  if (nonsense.some((p) => trimmed.includes(p))) {
    return true;
  }
  return false;
};

const extractMessageText = (ctx: CustomContext): string | undefined => {
  const message = ctx.message;
  if (message && 'text' in message) {
    const payload = message as { text?: string };
    return payload.text?.trim();
  }
  return undefined;
};

const sendChunkedReplies = async (
  ctx: CustomContext,
  text: string,
  keyboard: ReturnType<typeof solutionStepKeyboard>
): Promise<void> => {
  const chunks = splitToTelegramChunks(text);
  for (let i = 0; i < chunks.length; i += 1) {
    const chunkKeyboard = i === chunks.length - 1 ? keyboard : undefined;
    await ctx.reply(chunks[i], chunkKeyboard);
  }
};




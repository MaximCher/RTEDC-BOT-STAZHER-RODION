import { Prisma } from '@prisma/client';
import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction } from '../../types/lead';
import { messages, getDirectionLabel } from '../messages';
import { analyzeCase } from '../../services/aiAssistant';
import { prisma } from '../../services/db';
import { logger } from '../../utils/logger';
import { classifyCase } from '../../services/classifier';
import { selectKnowledgeForContext, KnowledgeDirection } from '../../services/knowledgeBase';
import { withCallbackGuard } from '../../utils/callbackGuard';

const directionToKnowledge: Record<Direction, KnowledgeDirection> = {
  finance: 'finance',
  logistics: 'logistics',
  payments: 'payments',
  analytics: 'analytics',
  other: 'export'
};

export const registerCaseHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:case:start:free',
    withCallbackGuard(async (ctx) => {
      ctx.session.flow = 'case_review';
      ctx.session.caseReview = {};
      await ctx.reply(messages.requestCaseText);
    })
  );
};

export const handleCaseText = async (ctx: CustomContext): Promise<boolean> => {
  if (ctx.session.flow !== 'case_review') {
    return false;
  }

  const rawText = extractMessageText(ctx);
  if (!rawText) {
    return false;
  }

  await ctx.reply(messages.caseAnalyzing);

  const guessedDirection = classifyCase(rawText);
  const knowledgeDirection = directionToKnowledge[guessedDirection] ?? 'general';
  const kbSelection = await selectKnowledgeForContext({
    direction: knowledgeDirection,
    freeText: rawText,
    maxChars: 2000
  });

  const aiResult = await analyzeCase(rawText, {
    direction: knowledgeDirection,
    kbContext: kbSelection?.context ?? null
  });
  const directionLabel = getDirectionLabel(aiResult.direction);

  ctx.session.lastCase = {
    text: rawText,
    direction: aiResult.direction,
    summary: aiResult.summary,
    advice: aiResult.advice,
    sources: kbSelection?.slugs
  };
  ctx.session.flow = 'idle';

  if (ctx.from?.id) {
    try {
      await prisma.caseLog.create({
        data: {
          userId: BigInt(ctx.from.id),
          text: rawText,
          direction: aiResult.direction,
          summary: aiResult.summary,
          advice: aiResult.advice,
          raw: {
            ai: aiResult,
            kbUsed: Boolean(kbSelection?.context),
            kbSources: kbSelection?.slugs ?? []
          } as unknown as Prisma.InputJsonValue
        }
      });
    } catch (error) {
      logger.error('Failed to persist case log', { error });
    }
  }

  await ctx.replyWithMarkdown(
    messages.caseAiResponse(directionLabel, aiResult.summary, aiResult.advice)
  );
  await ctx.replyWithMarkdown(messages.caseClosing, {
    reply_markup: {
      inline_keyboard: [
        [{ text: messages.caseCta, callback_data: 'srvt:lead:start:case' }],
        [{ text: 'В меню', callback_data: 'srvt:menu:open:root' }]
      ]
    }
  });

  return true;
};

const extractMessageText = (ctx: CustomContext): string | undefined => {
  const message = ctx.message;
  if (message && 'text' in message) {
    const payload = message as { text?: string };
    return payload.text?.trim();
  }
  return undefined;
};




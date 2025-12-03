import { Context } from 'telegraf';
import { logger } from './logger';
import { messages } from '../bot/messages';

type ActionHandler<C extends Context> = (ctx: C) => Promise<void>;

export const withCallbackGuard = <C extends Context>(
  handler: ActionHandler<C>
): ActionHandler<C> => {
  return async (ctx: C) => {
    const hasCallback = 'callbackQuery' in ctx && ctx.callbackQuery?.id;

    if (hasCallback) {
      try {
        await ctx.answerCbQuery();
      } catch (error) {
        logger.warn('Failed to answer callback query', {
          error: error instanceof Error ? { message: error.message } : error
        });
      }
    }

    try {
      await handler(ctx);
    } catch (error) {
      logger.error('Callback handler failed', {
        error: error instanceof Error ? { message: error.message, stack: error.stack } : error
      });

      try {
        await ctx.reply(messages.technicalIssue);
      } catch (replyError) {
        logger.error('Failed to notify user about error', {
          error: replyError instanceof Error ? { message: replyError.message } : replyError
        });
      }
    }
  };
};


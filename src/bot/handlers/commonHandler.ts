import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { resetFlow } from '../../types/session';
import { mainMenuKeyboard } from '../keyboards/mainMenu';
import { messages } from '../messages';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { logger } from '../../utils/logger';

export const registerCommonHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:flow:back',
    withCallbackGuard(async (ctx) => {
      try {
        resetFlow(ctx.session, 'idle');
      } catch (error) {
        logger.error('flow_back_reset_failed', { error });
      }

      try {
        await ctx.editMessageReplyMarkup(undefined);
      } catch (error) {
        logger.warn('flow_back_edit_markup_failed', { error });
      }

      await ctx.reply(messages.flowBackToMenu, mainMenuKeyboard());
    })
  );
};


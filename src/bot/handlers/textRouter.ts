import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { handleLeadText } from './leadHandler';
import { handleCaseText } from './caseHandler';
import { messages } from '../messages';
import { mainMenuKeyboard } from '../keyboards/mainMenu';

export const registerTextRouter = (bot: Telegraf<CustomContext>) => {
  bot.on('text', async (ctx, next) => {
    if (await handleLeadText(ctx)) {
      return;
    }

    if (await handleCaseText(ctx)) {
      return;
    }

    await ctx.reply(messages.fallback, mainMenuKeyboard());
    if (next) {
      await next();
    }
  });
};


import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { handleLeadText } from './leadHandler';
import { handleSolutionText } from './caseHandler';
import { handleSubsidySolutionText } from './subsidyHandler';
import { handleServiceDialogText } from './serviceDialogHandler';
import { messages } from '../messages';
import { mainMenuKeyboard } from '../keyboards/mainMenu';

export const registerTextRouter = (bot: Telegraf<CustomContext>) => {
  bot.on('text', async (ctx, next) => {
    if (await handleLeadText(ctx)) {
      return;
    }

    if (await handleSubsidySolutionText(ctx)) {
      return;
    }

    if (await handleServiceDialogText(ctx)) {
      return;
    }

    if (await handleSolutionText(ctx)) {
      return;
    }

    await ctx.reply(messages.fallback, mainMenuKeyboard());
    if (next) {
      await next();
    }
  });
};


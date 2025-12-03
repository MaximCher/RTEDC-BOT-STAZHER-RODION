import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { mainMenuKeyboard } from '../keyboards/mainMenu';
import { messages } from '../messages';
import { initialSessionState } from '../../types/session';
import { withCallbackGuard } from '../../utils/callbackGuard';

export const registerMenuHandlers = (bot: Telegraf<CustomContext>) => {
  bot.start(async (ctx) => {
    ctx.setSession(initialSessionState());
    await ctx.reply(messages.welcome(ctx.from?.first_name), mainMenuKeyboard());
  });

  bot.action(
    'srvt:menu:open:root',
    withCallbackGuard(async (ctx) => {
      ctx.setSession(initialSessionState());
      await ctx.reply(messages.mainMenuHint, mainMenuKeyboard());
    })
  );
};




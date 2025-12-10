import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { mainMenuKeyboard } from '../keyboards/mainMenu';
import { messages } from '../messages';
import { initialSessionState } from '../../types/session';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { getUserCasesByTelegramId } from '../../services/bitrixClient';

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

  bot.action(
    'srvt:cases:list',
    withCallbackGuard(async (ctx) => {
      const tgId = ctx.from?.id;
      if (!tgId) {
        await ctx.reply('Не удалось определить ваш Telegram ID. Попробуйте позже.');
        return;
      }
      const cases = await getUserCasesByTelegramId(tgId, 10);
      if (!cases.length) {
        await ctx.reply(
          'Пока обращений нет. Вы можете оставить первый запрос через разделы «Подбор решения», «Субсидии» или «Услуги СРВТ».',
          mainMenuKeyboard()
        );
        return;
      }
      let text = '📂 *Ваши кейсы в СРВТ:*\n\n';
      for (const c of cases) {
        text += `• #${c.id} — ${c.title}\n`;
        text += `  Статус: ${c.status}\n`;
        text += `  Создан: ${c.created}\n\n`;
      }
      await ctx.reply(text, { parse_mode: 'Markdown' });
    })
  );
};




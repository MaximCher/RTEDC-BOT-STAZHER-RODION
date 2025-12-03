import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction } from '../../types/lead';
import { servicesMenuKeyboard, serviceCtaKeyboard } from '../keyboards/services';
import { messages, getDirectionLabel } from '../messages';
import { startLeadForm } from './leadHandler';
import { withCallbackGuard } from '../../utils/callbackGuard';

export const registerServicesHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:services:open:root',
    withCallbackGuard(async (ctx) => {
      await ctx.reply(messages.servicesIntro, servicesMenuKeyboard());
    })
  );

  bot.action(
    /^srvt:services:view:(?<direction>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const direction = (ctx.match?.groups?.direction as Direction) ?? 'other';
      const body = `${messages.serviceDescription(direction)}\n\n${messages.serviceCta}`;
      await ctx.reply(body, serviceCtaKeyboard(direction));
    })
  );

  bot.action(
    /^srvt:services:lead:(?<direction>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const direction = (ctx.match?.groups?.direction as Direction) ?? 'other';
      await startLeadForm(ctx, {
        scenario: `service_${direction}`,
        direction,
        metadata: { service: getDirectionLabel(direction) }
      });
    })
  );
};




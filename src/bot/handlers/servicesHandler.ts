import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction } from '../../types/lead';
import {
  servicesMenuKeyboard,
  serviceCtaKeyboard,
  financeServiceKeyboard
} from '../keyboards/services';
import { messages, getDirectionLabel } from '../messages';
import { startLeadForm } from './leadHandler';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { resetFlow } from '../../types/session';
import { isServiceCategory, serviceCategoryToDirection } from '../../config/servicePlaybook';
import { startServiceDialog } from './serviceDialogHandler';

export const registerServicesHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:services:open:root',
    withCallbackGuard(async (ctx) => {
      resetFlow(ctx.session);
      await ctx.reply(messages.servicesIntro, servicesMenuKeyboard());
    })
  );

  bot.action(
    /^srvt:services:view:(?<category>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const rawCategory = ctx.match?.groups?.category ?? '';
      if (isServiceCategory(rawCategory)) {
        await startServiceDialog(ctx, rawCategory);
        return;
      }
      const direction = (rawCategory as Direction) ?? 'other';
      const body = `${messages.serviceDescription(direction)}\n\n${messages.serviceCta}`;
      const keyboard =
        direction === 'finance' ? financeServiceKeyboard() : serviceCtaKeyboard(direction);
      await ctx.reply(body, keyboard);
    })
  );

  bot.action(
    /^srvt:services:lead:(?<slug>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const slug = ctx.match?.groups?.slug ?? 'other';
      const serviceState = ctx.session.serviceDialog;
      const direction = isServiceCategory(slug)
        ? serviceCategoryToDirection(slug)
        : ((slug as Direction) ?? 'other');
      const metadata =
        serviceState && (!isServiceCategory(slug) || serviceState.category === slug)
          ? {
              serviceCategory: serviceState.category,
              serviceDialog: serviceState.dialog.slice(-10),
              serviceTurnCount: serviceState.turnCount
            }
          : undefined;
      await startLeadForm(ctx, {
        scenario: `service_${slug}`,
        direction,
        metadata: {
          ...(metadata ?? {}),
          service: getDirectionLabel(direction)
        }
      });
    })
  );
};




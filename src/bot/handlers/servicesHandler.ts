import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import {
  servicesMenuKeyboard
} from '../keyboards/services';
import { messages } from '../messages';
import { startLeadForm } from './leadHandler';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { resetFlow } from '../../types/session';
import {
  isServiceCategory,
  serviceCategoryToDirection,
  SERVICE_PLAYBOOK
} from '../../config/servicePlaybook';
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
      if (!isServiceCategory(rawCategory)) {
        await ctx.answerCbQuery('Направление временно недоступно', { show_alert: true });
        return;
      }
      await startServiceDialog(ctx, rawCategory);
    })
  );

  bot.action(
    /^srvt:services:lead:(?<slug>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const slug = ctx.match?.groups?.slug ?? 'other';
      const serviceState = ctx.session.serviceDialog;
      const playbook = isServiceCategory(slug) ? SERVICE_PLAYBOOK[slug] : undefined;
      const direction = playbook ? serviceCategoryToDirection(playbook.category) : 'other';
      const metadata =
        playbook && serviceState && serviceState.category === slug
          ? {
              serviceCategory: serviceState.category,
              serviceDialog: serviceState.dialog.slice(-10),
              serviceTurnCount: serviceState.turnCount,
              serviceType: serviceState.managerLabel,
              serviceOffer: serviceState.offer,
              serviceDescription: serviceState.description,
              serviceClarifyQuestion: serviceState.clarifyQuestion,
              serviceFirstInput: serviceState.firstInput,
              serviceClarification: serviceState.clarification,
              service: serviceState.managerLabel
            }
          : playbook
            ? {
                serviceCategory: playbook.category,
                serviceType: playbook.managerLabel,
                serviceOffer: playbook.offer,
                serviceDescription: playbook.description,
                serviceClarifyQuestion: playbook.clarifyQuestion,
                service: playbook.managerLabel
              }
            : undefined;
      await startLeadForm(ctx, {
        scenario: playbook?.leadScenario ?? `service_${slug}`,
        direction,
        metadata: {
          ...(metadata ?? {})
        }
      });
    })
  );
};




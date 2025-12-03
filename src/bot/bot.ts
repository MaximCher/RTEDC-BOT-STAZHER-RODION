import { Telegraf } from 'telegraf';
import { CustomContext } from '../types/context';
import { sessionMiddleware } from './middlewares/sessionMiddleware';
import { registerMenuHandlers } from './handlers/menuHandler';
import { registerQuizHandlers } from './handlers/quizHandler';
import { registerServicesHandlers } from './handlers/servicesHandler';
import { registerCaseHandlers } from './handlers/caseHandler';
import { registerLeadHandlers } from './handlers/leadHandler';
import { registerSubsidyHandlers } from './handlers/subsidyHandler';
import { registerTextRouter } from './handlers/textRouter';
import { logger } from '../utils/logger';

export const createBot = (token: string): Telegraf<CustomContext> => {
  const bot = new Telegraf<CustomContext>(token);

  bot.use(sessionMiddleware());

  registerMenuHandlers(bot);
  registerLeadHandlers(bot);
  registerQuizHandlers(bot);
  registerServicesHandlers(bot);
  registerCaseHandlers(bot);
  registerSubsidyHandlers(bot);
  registerTextRouter(bot);

  bot.catch((error, ctx) => {
    logger.error('Bot error', { error, update: ctx.update });
  });

  return bot;
};




import { createBot } from './bot/bot';
import { runtimeConfig } from './config/runtimeConfig';
import { logger } from './utils/logger';

const { botToken } = runtimeConfig;

if (!botToken) {
  throw new Error('BOT_TOKEN is not set. Provide it via environment variables.');
}

const bot = createBot(botToken);

bot
  .launch()
  .then(() => logger.info('SRVT Assistant launched'))
  .catch((error) => {
    logger.error('Failed to launch bot', { error });
    process.exit(1);
  });

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));




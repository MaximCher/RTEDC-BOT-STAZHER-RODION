import 'dotenv/config';

export const runtimeConfig = {
  botToken: process.env.BOT_TOKEN ?? '',
  adminChatId: process.env.ADMIN_CHAT_ID,
  bitrixWebhookUrl: process.env.BITRIX_WEBHOOK_URL ?? '',
  bitrixResponsibleId: (() => {
    const raw = process.env.BITRIX_RESPONSIBLE_DEFAULT_ID;
    if (!raw) {
      return undefined;
    }
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  })()
};




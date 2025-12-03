import 'dotenv/config';

export const runtimeConfig = {
  botToken: process.env.BOT_TOKEN ?? '',
  adminChatId: process.env.ADMIN_CHAT_ID
};




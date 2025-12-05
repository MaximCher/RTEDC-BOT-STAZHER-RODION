import { Markup } from 'telegraf';

type InlineButton = ReturnType<typeof Markup.button.callback>;

const backButton = (): InlineButton =>
  Markup.button.callback('⬅ Вернуться назад', 'srvt:flow:back');

export const commonBackKeyboard = (rows: InlineButton[][]) =>
  Markup.inlineKeyboard([...rows, [backButton()]]);


import { Markup } from 'telegraf';

export const leadConfirmKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('Отправить', 'srvt:lead:submit:confirm')],
    [Markup.button.callback('Заполнить заново', 'srvt:lead:restart:form')]
  ]);

export const backToMenuKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('Вернуться в меню', 'srvt:menu:open:root')]
  ]);




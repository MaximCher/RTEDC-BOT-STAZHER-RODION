import { Markup } from 'telegraf';

export const mainMenuKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('Получить помощь', 'srvt:quiz:start:main')],
    [Markup.button.callback('Проверить мой кейс', 'srvt:case:start:free')],
    [Markup.button.callback('Рассчитать субсидию', 'srvt:subsidy:start:init')],
    [Markup.button.callback('Услуги СРВТ', 'srvt:services:open:root')],
    [Markup.button.callback('Связаться с менеджером', 'srvt:lead:start:manager')]
  ]);




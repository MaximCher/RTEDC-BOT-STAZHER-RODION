import { Markup } from 'telegraf';

export const mainMenuKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('🧭 Подобрать решение', 'srvt:solution:start:free')],
    [Markup.button.callback('📋 Услуги СРВТ', 'srvt:services:open:root')],
    [Markup.button.callback('👨‍💼 Связаться с экспертом', 'srvt:lead:start:manager')],
    [
      Markup.button.callback(
        '🤝 Вступить в клуб СРВТ.РФ',
        'srvt:lead:start:club'
      )
    ],
    [
      Markup.button.callback('🎓 Академия СРВТ.РФ', 'srvt:lead:start:academy')
    ]
  ]);




import { Markup } from 'telegraf';
import { commonBackKeyboard } from './common';

const baseRows = () => [
  [
    Markup.button.callback('⌛ Я подожду', 'srvt:solution:wait:noop'),
    Markup.button.callback('📩 Отправить данные эксперту', 'srvt:lead:start:solution')
  ]
];

export const solutionStepKeyboard = (_aiReady: boolean) => commonBackKeyboard(baseRows());


import { Markup } from 'telegraf';
import { Direction } from '../../types/lead';

const directions: { direction: Direction; label: string }[] = [
  { direction: 'finance', label: 'Финансирование' },
  { direction: 'logistics', label: 'Логистика' },
  { direction: 'payments', label: 'Платежи' },
  { direction: 'analytics', label: 'Проверка партнера' },
  { direction: 'other', label: 'Другое' }
];

export const quizDirectionKeyboard = () =>
  Markup.inlineKeyboard([
    ...directions.map(({ direction, label }) => [
      Markup.button.callback(label, `srvt:quiz:direction:${direction}`)
    ]),
    [Markup.button.callback('Рассчитать субсидию', 'srvt:subsidy:start:init')],
    [Markup.button.callback('Назад', 'srvt:menu:open:root')]
  ]);

export const quizAnswerKeyboard = (
  questionKey: string,
  options: { label: string; value: string }[]
) =>
  Markup.inlineKeyboard([
    ...options.map((option) => [
      Markup.button.callback(
        option.label,
        `srvt:quiz:answer:${questionKey}__${option.value}`
      )
    ])
  ]);




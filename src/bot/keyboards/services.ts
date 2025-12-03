import { Markup } from 'telegraf';
import { Direction } from '../../types/lead';

const serviceOrder: Direction[] = [
  'finance',
  'logistics',
  'payments',
  'analytics',
  'other'
];

export const servicesMenuKeyboard = () =>
  Markup.inlineKeyboard([
    ...serviceOrder.map((direction) => [
      Markup.button.callback(
        serviceButtonLabel(direction),
        `srvt:services:view:${direction}`
      )
    ]),
    [Markup.button.callback('Назад', 'srvt:menu:open:root')]
  ]);

const serviceButtonLabel = (direction: Direction): string => {
  switch (direction) {
    case 'finance':
      return 'Финансирование';
    case 'logistics':
      return 'Логистика';
    case 'payments':
      return 'Платежи';
    case 'analytics':
      return 'Проверка партнера';
    case 'other':
    default:
      return 'Выход на внешние рынки';
  }
};

export const serviceCtaKeyboard = (direction: Direction) =>
  Markup.inlineKeyboard([
    [
      Markup.button.callback(
        'Оставить заявку',
        `srvt:services:lead:${direction}`
      )
    ],
    [Markup.button.callback('Назад к услугам', 'srvt:services:open:root')]
  ]);




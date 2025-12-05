import { Markup } from 'telegraf';
import { Direction } from '../../types/lead';
import { ServiceCategory } from '../../types/service';
import { SERVICE_MENU_ITEMS, SERVICE_PLAYBOOK } from '../../config/servicePlaybook';

export const servicesMenuKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('💰 Подбор субсидий с ИИ', 'srvt:subsidy:start:ai')],
    ...SERVICE_MENU_ITEMS.map(({ category, label }) => [
      Markup.button.callback(label, `srvt:services:view:${category}`)
    ]),
    [Markup.button.callback('⬅️ В главное меню', 'srvt:menu:open:root')]
  ]);

export const financeServiceKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('💰 Подбор субсидий с ИИ', 'srvt:subsidy:start:ai')],
    [Markup.button.callback('✍️ Оставить заявку', 'srvt:services:lead:finance')],
    [Markup.button.callback('⬅️ Назад к услугам', 'srvt:services:open:root')]
  ]);

export const serviceCtaKeyboard = (direction: Direction) =>
  Markup.inlineKeyboard([
    [
      Markup.button.callback('✍️ Оставить заявку', `srvt:services:lead:${direction}`)
    ],
    [Markup.button.callback('⬅️ Назад к услугам', 'srvt:services:open:root')]
  ]);

const categoryLeadKey = (category: ServiceCategory): string => category;

export const serviceDialogKeyboard = (
  category: ServiceCategory,
  _variant: 'clarify' | 'cta'
) => {
  const buttons = [];
  buttons.push([
    Markup.button.callback(
      '📩 Отправить данные эксперту',
      `srvt:services:lead:${categoryLeadKey(category)}`
    )
  ]);
  buttons.push([Markup.button.callback('↩️ Вернуться назад', 'srvt:menu:open:root')]);
  return Markup.inlineKeyboard(buttons);
};




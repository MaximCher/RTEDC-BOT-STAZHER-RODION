import { Markup } from 'telegraf';
import { ServiceCategory } from '../../types/service';
import { SERVICE_MENU_ITEMS, SERVICE_PLAYBOOK } from '../../config/servicePlaybook';

export const servicesMenuKeyboard = () =>
  Markup.inlineKeyboard([
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[0].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[0].category}`
      )
    ],
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[1].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[1].category}`
      )
    ],
    [Markup.button.callback('🎯 Проверить возможность получения субсидии', 'srvt:subsidy:start:ai')],
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[2].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[2].category}`
      )
    ],
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[3].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[3].category}`
      )
    ],
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[4].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[4].category}`
      )
    ],
    [
      Markup.button.callback(
        SERVICE_MENU_ITEMS[5].label,
        `srvt:services:view:${SERVICE_MENU_ITEMS[5].category}`
      )
    ],
    [Markup.button.callback('↩ Вернуться назад', 'srvt:menu:open:root')]
  ]);

const categoryLeadKey = (category: ServiceCategory): string => category;

export const serviceDialogKeyboard = (category: ServiceCategory) =>
  Markup.inlineKeyboard([
    [
      Markup.button.callback(
        '⏳ Я подожду',
        `srvt:services:ask:${categoryLeadKey(category)}`
      ),
      Markup.button.callback(
        '📝 Отправить данные эксперту',
        `srvt:services:lead:${categoryLeadKey(category)}`
      )
    ],
    [Markup.button.callback('↩ Вернуться назад', 'srvt:services:open:root')]
  ]);




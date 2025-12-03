import { Markup } from 'telegraf';

export interface KeyboardOption {
  label: string;
  value: string;
}

export const subsidyKeyboard = (action: string, options: KeyboardOption[]) =>
  Markup.inlineKeyboard(
    options.map((option) => [
      Markup.button.callback(option.label, `srvt:subsidy:${action}:${option.value}`)
    ])
  );

export const subsidyResultKeyboard = () =>
  Markup.inlineKeyboard([
    [Markup.button.callback('Оставить заявку на оформление', 'srvt:lead:start:subsidy')],
    [Markup.button.callback('В главное меню', 'srvt:menu:open:root')]
  ]);




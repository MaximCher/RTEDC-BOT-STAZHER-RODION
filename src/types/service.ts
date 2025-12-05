export type ServiceCategory =
  | 'counterparty'
  | 'logistics'
  | 'payments'
  | 'finance_tools'
  | 'it_scale'
  | 'expansion';

export const serviceCategoryLabels: Record<ServiceCategory, string> = {
  counterparty: 'Проверка контрагента',
  logistics: 'Импорт и логистика',
  payments: 'Платежи и валютный контроль',
  finance_tools: 'Финансовые инструменты',
  it_scale: 'IT / масштабирование',
  expansion: 'Выход на зарубежные рынки'
};



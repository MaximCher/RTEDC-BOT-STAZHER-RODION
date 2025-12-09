export type ServiceCategory =
  | 'international_transactions'
  | 'loans'
  | 'logistics'
  | 'negotiations'
  | 'translations'
  | 'analytics';

export const serviceCategoryLabels: Record<ServiceCategory, string> = {
  international_transactions: 'Международные транзакции',
  loans: 'Льготные кредиты',
  logistics: 'Международная логистика',
  negotiations: 'Сопровождение переговоров',
  translations: 'Лингвистические переводы',
  analytics: 'Аналитика ВЭД и проверка контрагентов'
};



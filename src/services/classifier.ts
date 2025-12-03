import { Direction } from '../types/lead';

const keywordMatrix: Record<Direction, string[]> = {
  finance: ['финанс', 'субсид', 'кредит', 'поддержка', 'инвести'],
  logistics: ['логист', 'доставка', 'склад', 'цепоч', 'транспорт'],
  payments: ['платеж', 'расчет', 'банк', 'оплата', 'валюта'],
  analytics: ['аналит', 'исслед', 'market', 'данн', 'benchmark'],
  other: []
};

export const classifyCase = (text: string): Direction => {
  const normalized = text.toLowerCase();

  for (const [direction, keywords] of Object.entries(keywordMatrix) as [
    Direction,
    string[]
  ][]) {
    if (!keywords.length) {
      continue;
    }

    if (keywords.some((keyword) => normalized.includes(keyword))) {
      return direction;
    }
  }

  return 'other';
};

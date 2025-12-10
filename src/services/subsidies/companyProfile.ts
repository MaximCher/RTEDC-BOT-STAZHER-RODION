export type CompanySector =
  | 'it'
  | 'industry'
  | 'agro'
  | 'tourism'
  | 'logistics'
  | 'finance'
  | 'other';

const sectorMatchers: Array<{ sector: CompanySector; patterns: RegExp[] }> = [
  {
    sector: 'it',
    patterns: [
      /айти/i,
      /\bit\b/i,
      /цифров/i,
      /софт/i,
      /приложен/i,
      /saas/i,
      /маркетплейс/i,
      /онлайн[-\s]?сервис/i
    ]
  },
  {
    sector: 'logistics',
    patterns: [/логист/i, /достав/i, /импорт/i, /экспорт/i, /таможн/i, /склад/i]
  },
  {
    sector: 'agro',
    patterns: [/агро/i, /сельхоз/i, /сельск.*хоз/i, /ферм/i, /животновод/i, /растениевод/i]
  },
  {
    sector: 'tourism',
    patterns: [/туризм/i, /гостиниц/i, /отел/i, /санатор/i, /турист/i, /глэмпинг/i]
  },
  {
    sector: 'finance',
    patterns: [/банк/i, /финанс/i, /кредит/i, /лизинг/i, /инвест/i, /страхован/i]
  },
  {
    sector: 'industry',
    patterns: [/завод/i, /производств/i, /станок/i, /оборудован/i, /промышлен/i]
  }
];

export function detectCompanySectorFromText(text: string): CompanySector {
  const normalized = text.toLowerCase();
  for (const matcher of sectorMatchers) {
    if (matcher.patterns.some((pattern) => pattern.test(normalized))) {
      return matcher.sector;
    }
  }
  return 'other';
}

export function normalizeProgramSectors(raw: string | string[] | null | undefined): CompanySector[] {
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const normalized = new Set<CompanySector>();

  const push = (sector: CompanySector) => normalized.add(sector);

  for (const value of values) {
    const token = (value ?? '').toString().toLowerCase();
    if (!token.trim()) continue;

    if (/[аи]т|цифров|информатик|софт|по\b/.test(token)) {
      push('it');
      continue;
    }
    if (/сельск|агро|апк|ферм|животновод|растениевод/.test(token)) {
      push('agro');
      continue;
    }
    if (/туриз|гостиниц|санатор|отел|глэмп/.test(token)) {
      push('tourism');
      continue;
    }
    if (/логист|транспорт|перевоз|склад/.test(token)) {
      push('logistics');
      continue;
    }
    if (/финанс|банк|кредит|лизинг|страхован/.test(token)) {
      push('finance');
      continue;
    }
    if (/производ|завод|станок|оборуд/.test(token)) {
      push('industry');
      continue;
    }
  }

  if (!normalized.size) {
    normalized.add('other');
  }

  return Array.from(normalized);
}


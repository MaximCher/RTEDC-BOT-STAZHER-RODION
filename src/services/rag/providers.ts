import path from 'path';
import { readFile } from 'fs/promises';
import { RagProgramRecord } from './types';
import { logger } from '../../utils/logger';
import { SubsidyCostType } from '../../types/subsidy';

const CSV_PATH = path.resolve(process.cwd(), 'src/data/subsidies_source.csv');
const CSV_CACHE_TTL = 5 * 60 * 1000;

let cache: { expiresAt: number; programs: RagProgramRecord[] } | null = null;

export const loadCsvPrograms = async (): Promise<RagProgramRecord[]> => {
  if (cache && cache.expiresAt > Date.now()) {
    return cache.programs;
  }
  try {
    const raw = await readFile(CSV_PATH, 'utf8');
    const rows = parseCsv(raw);
    if (!rows.length) {
      cache = { expiresAt: Date.now() + CSV_CACHE_TTL, programs: [] };
      return [];
    }
    const header = rows.shift()!.map((cell) => cell.trim().toLowerCase());
    const programs = rows
      .map((row) => mapRowToRecord(header, row))
      .filter((item): item is RagProgramRecord => Boolean(item));
    cache = { expiresAt: Date.now() + CSV_CACHE_TTL, programs };
    return programs;
  } catch (error) {
    logger.warn('csv_rag_failed', {
      error: error instanceof Error ? error.message : error,
      path: CSV_PATH
    });
    cache = { expiresAt: Date.now() + CSV_CACHE_TTL, programs: [] };
    return [];
  }
};

const parseCsv = (raw: string): string[][] => {
  const rows: string[][] = [];
  let row: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < raw.length; i += 1) {
    const char = raw[i];

    if (char === '"') {
      const next = raw[i + 1];
      if (inQuotes && next === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ';' && !inQuotes) {
      row.push(current);
      current = '';
      continue;
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && raw[i + 1] === '\n') {
        i += 1;
      }
      row.push(current);
      if (row.some((cell) => cell.trim().length)) {
        rows.push(row);
      }
      row = [];
      current = '';
      continue;
    }

    current += char;
  }

  if (current.length || row.length) {
    row.push(current);
    if (row.some((cell) => cell.trim().length)) {
      rows.push(row);
    }
  }

  return rows;
};

const mapRowToRecord = (header: string[], row: string[]): RagProgramRecord | null => {
  const data: Record<string, string> = {};
  header.forEach((key, idx) => {
    data[key] = row[idx]?.trim() ?? '';
  });

  const code = data.code;
  const title = data.title;
  if (!code || !title) {
    return null;
  }

  const context = {
    code,
    title,
    description: data.description ?? ''
  };

  const categoryInfo = mapCategory(data.category, context);
  const costTypes = detectCostTypes(title, data.description);
  const coverageRate = parsePercent(data.compensation_percent);
  const maxAmount = parseMoney(data.limit_amount);
  const links = splitLinks(data.links);
  const keywordSet = new Set(
    buildKeywords([data.category, title, data.description, data.notes, code])
  );
  keywordSet.add(categoryInfo.sector);
  costTypes.forEach((type) => keywordSet.add(type));
  if (categoryInfo.isExport) {
    keywordSet.add('экспорт');
    keywordSet.add('export');
  }

  return {
    code,
    title,
    description: data.description ?? '',
    sectors: [categoryInfo.sector],
    costTypes: costTypes.length ? costTypes : ['other'],
    regions: [categoryInfo.region],
    keywords: Array.from(keywordSet),
    isExport: categoryInfo.isExport,
    minBudget: null,
    maxBudget: maxAmount,
    coverageRate,
    maxAmount,
    sourceUrl: links[0] ?? null,
    conditions: data.application_period || null,
    notes: data.notes || null,
    links,
    source: 'csv_manual'
  };
};

const splitLinks = (value?: string): string[] =>
  (value ?? '')
    .split(/[,;]/)
    .map((link) => link.trim())
    .filter(Boolean);

const parsePercent = (value?: string): number | null => {
  if (!value) {
    return null;
  }
  const normalized = Number(value.replace(',', '.'));
  if (!Number.isFinite(normalized)) {
    return null;
  }
  return normalized >= 1 ? normalized / 100 : normalized;
};

const parseMoney = (value?: string): number | null => {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/\s+/g, '').replace(',', '.');
  const multiplier =
    /млрд/i.test(value) ? 1_000_000_000 : /млн|kk|кк/i.test(value) ? 1_000_000 : /тыс|k|к/i.test(value) ? 1_000 : 1;
  const digits = normalized.replace(/[^0-9.]/g, '');
  const parsed = Number(digits);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.round(parsed * multiplier);
};

const buildKeywords = (chunks: Array<string | undefined>): string[] => {
  const joined = chunks
    .filter((chunk): chunk is string => Boolean(chunk && chunk.trim()))
    .join(' ')
    .toLowerCase();
  return Array.from(
    new Set(
      joined
        .split(/\s+/)
        .map((token) => token.trim())
        .filter(Boolean)
    )
  );
};

const detectCostTypes = (title?: string, description?: string): SubsidyCostType[] => {
  const text = `${title ?? ''} ${description ?? ''}`.toLowerCase();
  const costTypes = new Set<SubsidyCostType>();

  if (/оборуд|станк|техник|машин/.test(text)) {
    costTypes.add('equipment');
  }
  if (/транспорт|логист|достав|склад/.test(text)) {
    costTypes.add('logistics');
  }
  if (/обуч|квалификац|тренинг|образов/.test(text)) {
    costTypes.add('training');
  }
  if (/маркет|продвиж|выстав|ярмарк|форум/.test(text)) {
    costTypes.add('marketing');
    costTypes.add('exhibitions');
  }
  if (/патент|сертифика|лиценз|омолога/.test(text)) {
    costTypes.add('certification');
  }
  if (/r&d|ниокр|разработ|исслед/.test(text)) {
    costTypes.add('r_and_d');
  }
  if (/зарп|фот|персонал|команда/.test(text)) {
    costTypes.add('payroll');
  }

  return Array.from(costTypes);
};

const mapCategory = (
  rawCategory: string | undefined,
  context: { code?: string; title?: string; description?: string }
): { sector: string; region: string; isExport: boolean } => {
  const category = (rawCategory ?? '').trim().toLowerCase();
  const title = (context.title ?? '').toLowerCase();
  const description = (context.description ?? '').toLowerCase();
  const code = (context.code ?? '').toLowerCase();

  if (!category) {
    return { sector: 'other', region: 'fo', isExport: false };
  }
  if (category.includes('экспорт')) {
    return { sector: 'export', region: 'fo', isExport: true };
  }
  if (category.includes('апк')) {
    return { sector: 'agro', region: 'fo', isExport: false };
  }
  if (category.includes('туризм') || title.includes('туризм')) {
    return { sector: 'tourism', region: 'fo', isExport: false };
  }
  if (category.includes('нко')) {
    return { sector: 'services', region: 'fo', isExport: false };
  }
  if (category.includes('пром') || title.includes('пром') || description.includes('пром')) {
    return { sector: 'manufacturing', region: 'fo', isExport: false };
  }
  if (category.includes('москва') || category.includes('мск') || code.startsWith('msk_')) {
    return { sector: 'it', region: 'moscow', isExport: false };
  }
  return { sector: 'other', region: 'fo', isExport: false };
};


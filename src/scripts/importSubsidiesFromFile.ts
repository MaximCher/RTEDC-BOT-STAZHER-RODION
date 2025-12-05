import path from 'path';
import fs from 'fs/promises';
import { readFileSync } from 'fs';
import * as XLSX from 'xlsx';
import { upsertPrograms, RawSubsidyProgram } from '../services/subsidyRepository';
import { logger } from '../utils/logger';

// Важно: исходный Excel/CSV должен быть сохранён в UTF-8 без дополнительного перекодирования.
const SOURCE_FILES = [
  path.resolve(process.cwd(), 'src', 'data', 'subsidies_source.xlsx'),
  path.resolve(process.cwd(), 'src', 'data', 'subsidies_source.csv')
];

const normalizeKey = (key: string): string =>
  key
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');

const FIELD_ALIASES: Record<keyof RawSubsidyProgram, string[]> = {
  code: ['code', 'код'],
  title: ['title', 'название'],
  description: ['description', 'описание'],
  costTypes: ['cost_types', 'costs', 'расходы', 'тип_затрат'],
  sectors: ['sectors', 'sector', 'отрасль', 'направление', 'category', 'категория'],
  regions: ['regions', 'region', 'регионы', 'регион'],
  keywords: ['keywords', 'теги', 'ключевые_слова'],
  isExport: ['requires_export', 'export', 'нужен_экспорт', 'is_export'],
  minBudget: ['min_budget', 'min_spend', 'минимальные_затраты'],
  maxBudget: ['max_budget', 'max_spend', 'максимальные_затраты'],
  coverageRate: ['coverage_rate', 'coverage', 'процент', 'compensation_percent'],
  maxAmount: ['max_amount', 'limit_amount', 'потолок', 'лимит'],
  conditions: ['conditions', 'условия'],
  recipient: ['recipient', 'получатели'],
  docsRequired: ['docs_required', 'документы'],
  notes: ['notes', 'примечания']
};

const normalizeText = (value: unknown): string => String(value ?? '').trim();

const ensureArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeText(item))
      .filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(/[,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return [String(value)];
  }
  return [];
};

const SECTOR_ALIASES: Record<string, string> = {
  it: 'it',
  'айти': 'it',
  'цифров': 'it',
  digital: 'it',
  technology: 'it',
  'технолог': 'it',
  'экспорт': 'export',
  export: 'export',
  'промышленность': 'manufacturing',
  industry: 'manufacturing',
  'логистика': 'logistics',
  logistics: 'logistics',
  'апк': 'agro',
  'агро': 'agro',
  'сельхоз': 'agro',
  'агротуризм': 'agrotourism',
  'туризм': 'tourism',
  'услуги': 'services',
  'сервис': 'services',
  'строительство': 'construction',
  'стройка': 'construction',
  education: 'education',
  'образование': 'education',
  healthcare: 'healthcare',
  'здравоохранение': 'healthcare',
  'мед': 'healthcare'
};

const REGION_ALIASES: Record<string, string> = {
  'мск': 'moscow',
  'москва': 'moscow',
  moskva: 'moscow',
  moscow: 'moscow',
  'спб': 'spb',
  'санкт-петербург': 'spb',
  'петербург': 'spb',
  'питер': 'spb',
  dfo: 'dfo',
  'дфо': 'dfo',
  'дальний': 'dfo',
  'дальневосточный': 'dfo',
  'россия': 'fo',
  rf: 'fo',
  ru: 'fo',
  russia: 'fo',
  'федеральный': 'fo'
};

const normalizeSectorTokens = (values: string[]): string[] =>
  Array.from(
    new Set(
      values
        .map((value) => {
          const normalized = value.toLowerCase();
          return SECTOR_ALIASES[normalized] ?? 'other';
        })
        .filter(Boolean)
    )
  );

const normalizeRegionTokens = (values: string[]): string[] =>
  Array.from(
    new Set(
      values.map((value) => {
        const normalized = value.toLowerCase();
        for (const [alias, region] of Object.entries(REGION_ALIASES)) {
          if (normalized.includes(alias)) {
            return region;
          }
        }
        return 'other';
      })
    )
  );

const parseBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value > 0;
  }
  if (typeof value === 'string') {
    const normalized = value.toLowerCase().trim();
    return ['true', 'yes', 'да', '1'].includes(normalized);
  }
  return false;
};

const parseCurrency = (value: unknown): number => {
  if (typeof value === 'number') {
    return Math.round(value);
  }
  if (typeof value === 'string') {
    const digits = value.replace(/[^0-9.-]+/g, '');
    const parsed = Number(digits);
    if (Number.isFinite(parsed)) {
      return Math.round(parsed);
    }
  }
  return 0;
};

const parseRub = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.round(value));
  }
  if (typeof value === 'string') {
    const digits = value.replace(/[^\d]/g, '');
    if (!digits) {
      return null;
    }
    const parsed = Number(digits);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const parseRatio = (value: unknown): number => {
  if (typeof value === 'number') {
    return value > 1 ? value / 100 : value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[^0-9.,-]+/g, '').replace(',', '.'));
    if (Number.isFinite(parsed)) {
      return parsed > 1 ? parsed / 100 : parsed;
    }
  }
  return 0;
};

const extractField = (
  record: Record<string, unknown>,
  key: keyof RawSubsidyProgram
): unknown => {
  const aliases = FIELD_ALIASES[key];
  for (const alias of aliases) {
    if (alias in record) {
      return record[alias];
    }
  }
  return undefined;
};

const mapRowToProgram = (
  record: Record<string, unknown>,
  index: number
): RawSubsidyProgram | null => {
  const code = normalizeText(extractField(record, 'code'));
  const title = normalizeText(extractField(record, 'title'));
  const description = normalizeText(extractField(record, 'description'));

  if (!code || !title || !description) {
    logger.warn('Skipping row without mandatory fields', { index, code, title });
    return null;
  }

  const costTypes = ensureArray(extractField(record, 'costTypes')).map((value) =>
    value.toLowerCase()
  );
  const sectors = normalizeSectorTokens(ensureArray(extractField(record, 'sectors')));
  const regions = normalizeRegionTokens(ensureArray(extractField(record, 'regions')));
  const keywords = ensureArray(extractField(record, 'keywords'));

  const minBudget = parseRub(extractField(record, 'minBudget'));
  const maxBudget = parseRub(extractField(record, 'maxBudget'));
  const maxAmount = parseCurrency(extractField(record, 'maxAmount'));
  const coverageRate = parseRatio(extractField(record, 'coverageRate'));

  const isExport = parseBoolean(extractField(record, 'isExport')) || sectors.includes('export');

  return {
    code,
    title,
    description,
    sectors,
    isExport,
    costTypes,
    regions,
    keywords,
    minBudget: minBudget ?? undefined,
    maxBudget: maxBudget ?? undefined,
    coverageRate,
    maxAmount: maxAmount || undefined,
    conditions: normalizeText(extractField(record, 'conditions')) || undefined,
    recipient: normalizeText(extractField(record, 'recipient')) || undefined,
    docsRequired: normalizeText(extractField(record, 'docsRequired')) || undefined,
    notes: normalizeText(extractField(record, 'notes')) || undefined
  };
};

const detectSourceFile = async (): Promise<string> => {
  for (const candidate of SOURCE_FILES) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // continue
    }
  }
  throw new Error('Не найден файл src/data/subsidies_source.xlsx или .csv');
};

const readRows = async (filePath: string): Promise<Record<string, unknown>[]> => {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.csv') {
    const content = readFileSync(filePath, 'utf8');
    return parseSheetRows(
      XLSX.read(content, {
        type: 'string',
        raw: false
      })
    );
  }

  const buffer = await fs.readFile(filePath);
  return parseSheetRows(
    XLSX.read(buffer, {
      type: 'buffer',
      raw: false
    })
  );
};

const parseSheetRows = (workbook: XLSX.WorkBook): Record<string, unknown>[] => {
  const [firstSheetName] = workbook.SheetNames;
  if (!firstSheetName) {
    return [];
  }
  const sheet = workbook.Sheets[firstSheetName];
  return XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
    defval: '',
    raw: false
  });
};

const normalizeRecords = (rows: Record<string, unknown>[]): Record<string, unknown>[] =>
  rows.map((row) => {
    const normalized: Record<string, unknown> = {};
    Object.entries(row).forEach(([key, value]) => {
      normalized[normalizeKey(String(key))] = value;
    });
    return normalized;
  });

const main = async () => {
  try {
    const sourceFile = await detectSourceFile();
    logger.info('Using subsidy source file', { sourceFile });
    const rawRows = await readRows(sourceFile);
    if (!rawRows.length) {
      throw new Error('В файле нет данных');
    }
    const normalized = normalizeRecords(rawRows);
    const headers = Object.keys(normalized[0] ?? {});
    logger.info('Detected columns', { headers });

    const programs: RawSubsidyProgram[] = [];
    normalized.forEach((record, index) => {
      const mapped = mapRowToProgram(record, index);
      if (mapped) {
        programs.push(mapped);
      }
    });

    logger.info('Subsidy import preview', {
      sample: programs.slice(0, 3).map((program) => ({
        code: program.code,
        title: program.title,
        minBudget: program.minBudget ?? null,
        maxBudget: program.maxBudget ?? null
      }))
    });

    await upsertPrograms(programs);
    logger.info('Subsidy import completed', { total: programs.length });
    process.exit(0);
  } catch (error) {
    logger.error('Subsidy import failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    process.exit(1);
  }
};

main();



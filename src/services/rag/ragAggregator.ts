import { SubsidyClassification, SubsidyProgram } from '../../types/subsidy';
import { stableHash } from '../../utils/hash';
import { loadCsvPrograms } from './providers';
import { RagProgramRecord } from './types';

const CACHE_TTL_MS = 10 * 60 * 1000;

interface RagCacheEntry {
  expiresAt: number;
  programs: SubsidyProgram[];
}

const ragCache = new Map<string, RagCacheEntry>();

export const fetchRemotePrograms = async (
  classification: SubsidyClassification
): Promise<SubsidyProgram[]> => {
  const cacheKey = buildCacheKey(classification);
  const cached = ragCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.programs;
  }

  const csvPrograms = await loadCsvPrograms();
  const matchedRecords = filterByClassification(csvPrograms, classification);
  const sourceRecords = matchedRecords.length ? matchedRecords : csvPrograms;

  const merged = mergePrograms(sourceRecords);
  ragCache.set(cacheKey, { expiresAt: Date.now() + CACHE_TTL_MS, programs: merged });
  return merged;
};

const mergePrograms = (records: RagProgramRecord[]): SubsidyProgram[] => {
  const deduped = new Map<string, SubsidyProgram>();
  records.forEach((record) => {
    const program = convertRecord(record);
    if (!deduped.has(program.code)) {
      deduped.set(program.code, program);
    }
  });
  return Array.from(deduped.values());
};

const convertRecord = (record: RagProgramRecord): SubsidyProgram => {
  const fallbackCode = `${record.source}-${stableHash(`${record.title}-${record.code}`)}`;
  const code = record.code || fallbackCode;
  const id = stableHash(`${record.source}:${code}`);

  return {
    id,
    code,
    title: record.title,
    description: record.description,
    direction: 'finance',
    sectors: record.sectors.length ? record.sectors : ['other'],
    costTypes: record.costTypes.length ? record.costTypes : ['other'],
    regions: record.regions.length ? record.regions : ['other'],
    keywords: record.keywords,
    isExport: record.isExport,
    minBudget: record.minBudget ?? null,
    maxBudget: record.maxBudget ?? null,
    coverageRate: record.coverageRate ?? null,
    maxAmount: record.maxAmount ?? null,
    conditions: record.conditions ?? null,
    recipient: record.recipient ?? null,
    docsRequired: record.docsRequired ?? null,
    notes: record.notes ?? record.links?.join(' | ') ?? record.sourceUrl ?? null
  };
};

const buildCacheKey = (classification: SubsidyClassification): string => {
  const payload = {
    sectors: classification.sectors,
    costTypes: classification.costTypes,
    region: classification.region,
    export: classification.export,
    budgetFrom: classification.budgetFrom,
    budgetTo: classification.budgetTo
  };
  return JSON.stringify(payload);
};

const buildKeywordSet = (classification: SubsidyClassification): string[] => {
  const keywords = new Set<string>();
  classification.sectors.forEach((sector) => keywords.add(sector));
  classification.costTypes.forEach((type) => keywords.add(type));

  if (typeof classification.export === 'boolean') {
    keywords.add(classification.export ? 'экспорт' : 'без экспорта');
  }

  const budget =
    classification.budgetTo ?? classification.budgetFrom ?? null;
  if (budget && budget > 0) {
    keywords.add(`${Math.round(budget / 1_000_000)} млн`);
  }

  return Array.from(keywords).filter(Boolean);
};

const filterByClassification = (
  records: RagProgramRecord[],
  classification: SubsidyClassification
): RagProgramRecord[] => {
  const searchKeywords = buildKeywordSet(classification);
  const budget = classification.budgetTo ?? classification.budgetFrom ?? null;

  return records.filter((record) => {
    const sectorMatch =
      !classification.sectors.length ||
      classification.sectors.some((sector) => record.sectors.includes(sector));

    const regionMatch =
      classification.region === 'unknown' ||
      record.regions.includes(classification.region) ||
      record.regions.includes('fo');

    const exportMatch =
      typeof classification.export !== 'boolean' ||
      record.isExport === classification.export ||
      !record.isExport;

    const budgetMatch = matchesBudget(record, budget);

    const keywordMatch =
      !searchKeywords.length ||
      searchKeywords.some((keyword) => record.keywords.includes(keyword.toLowerCase()));

    return sectorMatch && regionMatch && exportMatch && budgetMatch && keywordMatch;
  });
};

const matchesBudget = (record: RagProgramRecord, budget: number | null): boolean => {
  if (!budget || budget <= 0) {
    return true;
  }
  const min = record.minBudget ?? 0;
  const max = record.maxAmount ?? Number.POSITIVE_INFINITY;

  if (min && budget < min * 0.5) {
    return false;
  }
  if (max !== Number.POSITIVE_INFINITY && budget > max * 1.2) {
    return false;
  }
  return true;
};


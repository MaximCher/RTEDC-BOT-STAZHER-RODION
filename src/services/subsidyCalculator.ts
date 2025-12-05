import {
  EstimatedProgram,
  HybridSubsidyInput,
  SubsidyClassification,
  SubsidyEstimationResult,
  SubsidyMatchScore,
  SubsidyProgram,
  SubsidyRegion
} from '../types/subsidy';
import { logger } from '../utils/logger';
import { getAllPrograms } from './subsidyRepository';

const CACHE_TTL_MS = 5 * 60 * 1000;
let cache: { data: SubsidyProgram[]; expiresAt: number } | null = null;

const loadPrograms = async (): Promise<SubsidyProgram[]> => {
  if (cache && cache.expiresAt > Date.now()) {
    return cache.data;
  }

  const programs = await getAllPrograms();
  cache = { data: programs, expiresAt: Date.now() + CACHE_TTL_MS };
  return programs;
};

export const calculateSubsidyResult = async (
  classification: SubsidyClassification
): Promise<SubsidyEstimationResult> => {
  const programs = await loadPrograms();
  const matches = findBestPrograms({ classification }, programs);

  if (!matches.length) {
    logger.info('subsidy_matches_empty', { classification });
    return {
      programs: [],
      metadataPrograms: [],
      hasAmountEstimate: false
    };
  }

  const metadataPrograms = matches.slice(0, 5).map(toEstimatedProgram);
  const positivePrograms = metadataPrograms.filter((program) => program.estimatedAmount > 0);

  if (shouldLogItMoscow(classification)) {
    logger.info('subsidy_calc_it_moscow', {
      classification,
      preview: positivePrograms.slice(0, 3)
    });
  }

  return {
    programs: positivePrograms.slice(0, 3),
    metadataPrograms,
    hasAmountEstimate: positivePrograms.length > 0
  };
};

export const findBestPrograms = (
  input: HybridSubsidyInput,
  allPrograms: SubsidyProgram[]
): SubsidyMatchScore[] => {
  const matches: SubsidyMatchScore[] = [];

  for (const program of allPrograms) {
    const match = scoreProgram(program, input.classification);
    if (!match) {
      continue;
    }
    logProgramMatch(program, input.classification, match);
    matches.push(match);
  }

  const validMatches = matches.filter((match) => match.score > 0);
  const sorted = (validMatches.length ? validMatches : matches).sort((a, b) => {
    if (b.score === a.score) {
      return b.estimatedAmount - a.estimatedAmount;
    }
    return b.score - a.score;
  });

  return sorted;
};

const SECTOR_SYNONYMS: Record<string, string[]> = {
  it: ['it', 'digital', 'technology', 'tech', 'инновац', 'цифров', 'software', 'development'],
  logistics: ['logistics', 'supply', 'freight', 'warehouse', 'склад', 'перевоз'],
  tourism: ['tourism', 'travel', 'hospitality', 'туризм', 'гостиниц', 'hospitality'],
  agrotourism: ['agrotourism', 'rural tourism', 'агротуризм', 'сельский туризм', 'tourism'],
  agro: ['agro', 'agriculture', 'сельхоз', 'агро', 'agrotourism'],
  export: ['export', 'вэд', 'экспорт'],
  services: ['services', 'service', 'сервис', 'услуг'],
  manufacturing: ['manufacturing', 'production', 'fabrication', 'производ'],
  construction: ['construction', 'строи', 'infrastructure'],
  education: ['education', 'обучен', 'edtech'],
  healthcare: ['health', 'medtech', 'healthcare', 'мед'],
  other: []
};

const sectorFamily = (sector: string): string[] => [
  sector,
  ...(SECTOR_SYNONYMS[sector] ?? [])
];

const sectorsMatch = (programSector: string, classificationSector: string): boolean => {
  const programFamily = new Set(sectorFamily(programSector));
  const classFamily = new Set(sectorFamily(classificationSector));
  if (programFamily.has(classificationSector) || classFamily.has(programSector)) {
    return true;
  }
  for (const token of classFamily) {
    if (programFamily.has(token)) {
      return true;
    }
  }
  return false;
};

const scoreProgram = (
  program: SubsidyProgram,
  classification: SubsidyClassification
): SubsidyMatchScore | null => {
  const programSectors = normalizeStrings(program.sectors);
  const excludes = normalizeStrings(classification.excludeSectors ?? []);
  if (programSectors.length && excludes.some((sector) => programSectors.includes(sector))) {
    return null;
  }

  let score = 0;

  const preferredSectors = normalizeStrings(classification.sectors ?? []);
  const sectorMatched = preferredSectors.some((clsSector) =>
    programSectors.some((progSector) => sectorsMatch(progSector, clsSector))
  );

  const programKeywords = normalizeStrings(program.keywords ?? []);
  const expandedSectorTokens = preferredSectors.flatMap((sector) => [
    sector,
    ...(SECTOR_SYNONYMS[sector] ?? [])
  ]);
  const classificationKeywords = Array.from(
    new Set([
      ...expandedSectorTokens,
      ...normalizeStrings(classification.costTypes),
      ...(classification.notes ? normalizeStrings(classification.notes.split(/\s+/)) : [])
    ])
  );

  let keywordMatch = false;
  if (!sectorMatched) {
    keywordMatch = classificationKeywords.some((token) => programKeywords.includes(token));
  }

  const exportAffinity = classification.export === true && Boolean(program.isExport);

  if (!sectorMatched && !keywordMatch && !exportAffinity) {
    return null;
  }

  if (sectorMatched) {
    score += 3;
  } else if (keywordMatch || exportAffinity) {
    score += 2;
  }

  if (classification.costTypes.length > 0) {
    const costTypes = normalizeStrings(program.costTypes);
    const desiredCostTypes = normalizeStrings(classification.costTypes);
    const costIntersection = intersects(costTypes, desiredCostTypes);
    score += costIntersection.length ? 3 : 0;
  }

  if (matchesRegion(program.regions, classification.region)) {
    score += 2;
  } else {
    return null;
  }

  if (program.isExport && classification.export === true) {
    score += 2;
  } else if (program.isExport && classification.export === false) {
    return null;
  }

  const budgetRange = resolveBudgetRange(classification);
  const budgetScore = scoreBudget(program, budgetRange);
  score += budgetScore;

  if (classification.notes && containsKeywords(classification.notes, program.keywords)) {
    score += 1;
  }

  const estimatedAmount = computeEstimatedAmount(program, budgetRange);

  return { program, score, estimatedAmount };
};

const matchesRegion = (programRegions: string[], region: SubsidyRegion): boolean => {
  if (region === 'unknown') {
    return true;
  }
  const normalized = mapRegionToProgramCode(region);
  const regions = normalizeStrings(programRegions);
  if (
    !regions.length ||
    regions.includes('any') ||
    regions.includes('all') ||
    regions.includes('nationwide') ||
    regions.includes('rf') ||
    regions.includes('other')
  ) {
    return true;
  }
  if (normalized === 'rf') {
    return regions.includes('rf') || regions.includes('all');
  }
  return regions.includes(normalized);
};

const scoreBudget = (program: SubsidyProgram, range: BudgetRange): number => {
  if (!range.min && !range.max && !range.point) {
    return 1;
  }

  const minBudget = program.minBudget ?? null;
  const maxBudget = program.maxBudget ?? null;

  const overlaps = rangesOverlap(range.min, range.max, minBudget, maxBudget);
  if (overlaps) {
    return 2;
  }

  const target = range.point ?? range.max ?? range.min;
  if (!target || !Number.isFinite(target)) {
    return 0;
  }

  if (minBudget && target < minBudget * 0.7) {
    return -1;
  }
  if (maxBudget && target > maxBudget * 1.3) {
    return 0;
  }
  return 1;
};

const containsKeywords = (notes: string, keywords: string[] = []): boolean => {
  if (!notes || !keywords.length) {
    return false;
  }
  const normalizedNotes = notes.toLowerCase();
  return keywords.some((keyword) => normalizedNotes.includes(keyword.toLowerCase()));
};

export const computeEstimatedAmount = (program: SubsidyProgram, range: BudgetRange): number => {
  const targetBudget =
    range.point ??
    range.max ??
    range.min ??
    program.minBudget ??
    program.maxAmount ??
    1_000_000;

  if (!targetBudget || targetBudget <= 0) {
    return program.maxAmount ?? 0;
  }

  if (!program.coverageRate || program.coverageRate <= 0) {
    if (program.maxAmount && program.maxAmount > 0) {
      return Math.min(program.maxAmount, targetBudget);
    }
    return 0;
  }

  const base = Math.round(targetBudget * program.coverageRate);
  const capped = program.maxAmount ? Math.min(base, program.maxAmount) : base;
  return capped;
};

const normalizeStrings = (values: string[]): string[] =>
  values
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);

const intersects = (left: string[], right: string[]): string[] => {
  if (!left.length || !right.length) {
    return [];
  }
  const leftSet = new Set(left.map((item) => item.trim().toLowerCase()));
  return right
    .map((item) => item.trim().toLowerCase())
    .filter((item) => leftSet.has(item));
};

const toEstimatedProgram = (match: SubsidyMatchScore): EstimatedProgram => ({
  programCode: match.program.code,
  title: match.program.title,
  estimatedAmount: match.estimatedAmount,
  coveragePercent: match.program.coverageRate
    ? Math.round((match.program.coverageRate ?? 0) * 100)
    : undefined,
  description: (match.program.description ?? '').split('\n')[0]?.trim(),
  score: match.score
});

const logProgramMatch = (
  program: SubsidyProgram,
  classification: SubsidyClassification,
  match: SubsidyMatchScore
): void => {
  logger.info('subsidy_program_match', {
    program: {
      code: program.code,
      title: program.title,
      coverageRate: program.coverageRate,
      maxAmount: program.maxAmount,
      minBudget: program.minBudget,
      maxBudget: program.maxBudget,
      sectors: program.sectors,
      costTypes: program.costTypes
    },
    classification,
    score: match.score,
    estimatedAmount: match.estimatedAmount
  });
};

interface BudgetRange {
  min: number | null;
  max: number | null;
  point: number | null;
}

const resolveBudgetRange = (classification: SubsidyClassification): BudgetRange => ({
  min:
    typeof classification.budgetFrom === 'number' && Number.isFinite(classification.budgetFrom)
      ? classification.budgetFrom
      : null,
  max:
    typeof classification.budgetTo === 'number' && Number.isFinite(classification.budgetTo)
      ? classification.budgetTo
      : null,
  point:
    typeof classification.budgetTo === 'number' && Number.isFinite(classification.budgetTo)
      ? classification.budgetTo
      : typeof classification.budgetFrom === 'number' && Number.isFinite(classification.budgetFrom)
        ? classification.budgetFrom
        : null
});

const rangesOverlap = (
  wantMin: number | null,
  wantMax: number | null,
  programMin: number | null,
  programMax: number | null
): boolean => {
  const min = wantMin ?? wantMax ?? null;
  const max = wantMax ?? wantMin ?? null;

  if (min === null && max === null) {
    return true;
  }

  if (programMin === null && programMax === null) {
    return true;
  }

  const desiredMin = min ?? max ?? 0;
  const desiredMax = max ?? min ?? desiredMin;
  const progMin = programMin ?? 0;
  const progMax = programMax ?? Number.MAX_SAFE_INTEGER;

  return desiredMax >= progMin && desiredMin <= progMax;
};

const shouldLogItMoscow = (classification: SubsidyClassification): boolean => {
  if (!classification.sectors.includes('it')) {
    return false;
  }
  if (classification.region !== 'moscow') {
    return false;
  }
  const range = resolveBudgetRange(classification);
  const approxBudget = range.point ?? range.max ?? range.min ?? 0;
  return approxBudget >= 1_000_000 && approxBudget <= 2_000_000;
};

const mapRegionToProgramCode = (region: SubsidyRegion): string => {
  switch (region) {
    case 'moscow':
      return 'msk';
    case 'spb':
      return 'spb';
    case 'dfo':
      return 'dfo';
    case 'fo':
      return 'rf';
    case 'other':
      return 'other';
    default:
      return '';
  }
};
